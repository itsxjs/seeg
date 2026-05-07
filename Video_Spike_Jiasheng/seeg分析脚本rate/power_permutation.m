%% Compute task-induced power. 
% adapoted from Li, Cao, et al.,2023. by Chenglu
% BOSC_tf_power,from the Better OSCillation detection (BOSC) library.
% zbaseline, from the function shared by Johnson EL, et al.,2018.

clear; clc;

%% ===== define parameters =====

% subject & data_dir
subj_id  = 'Sub004';
data_dir = 'E:\1_Chenglu\IM_sEEG_Chenglu\Data\Processed\LFP\Sub004';  % EEG .set 文件所在路径

epoch_files = { ...
    sprintf('%s_cue_epoch_clean.set', subj_id), ...
    sprintf('%s_target_epoch_clean.set', subj_id) ...
};
lock_types = {'cue','target'};

% Channel Selection
want_chans = {'POL B4','POL B5','F2-Ref'};
% 001:'POL B1','POL B2','POL B3','POL E1','POL E2','POL E3','POL E5','POL E6','POL E7'
% 004:'POL B4','POL B5','F1-Ref','F2-Ref'
% 005:'A1-Ref','POL B2','POL E3','POL E4','POL E5','F2-Ref','F3-Ref','F4-Ref'
% 007:'POL A4','POL A5','POL A6','POL B6','POL H6','POL H7','POL H8'
% 008:'A2-Ref','POL A3','POL A4','POL A7','POL B3'


% analysis window（ms）
baseline_ref = [-500 0];
baseline_ref_s = [-0.5 0];
analysis_win_cue  = [-500 2400];
analysis_win_tgt  = [-500 2500];

% define parameters
freqs      = 1:150;     % 1..150 Hz
num_cycles = logspace(log10(3), log10(12), length(freqs));  % Morlet cycles
n_freqs    = numel(freqs);
n_bs  = 1000;           % 置换次数
rng(42);                % 随机参数

fprintf('频率与对应的Morlet cycles:\n');
for fi = 1:length(freqs)
    fprintf('Freq = %3d Hz  →  %.2f cycles\n', freqs(fi), num_cycles(fi));
end

% downsampling
ds_ms = 50;         % 50 ms

%% ===== 循环 cue / target =====
mu_baseline = []; sigma_baseline = [];

for iL = 1:2
    lock_type = lock_types{iL};
    EEG = pop_loadset('filename', epoch_files{iL}, 'filepath', data_dir);

    % ---- ① analysis_channel selection ----
    have_labels = {EEG.chanlocs.labels};
    keep = intersect(want_chans, have_labels, 'stable');
    if numel(keep) < numel(want_chans)
        warning('以下通道缺失，将忽略：%s', strjoin(setdiff(want_chans, keep),' , '));
    end
    EEG = pop_select(EEG, 'channel', keep);

    srate    = EEG.srate;
    n_trials = EEG.trials;
    n_chans  = EEG.nbchan;
    tms_all  = EEG.times;         % ms
    nyq      = srate/2;
    freqs_eff = freqs(freqs < nyq - 1e-6);
    n_freqs_eff = numel(freqs_eff);

    % ---- ② analysis_window selection ----
    switch lock_type
        case 'cue'
            analysis_win = analysis_win_cue;
        case 'target'
            analysis_win = analysis_win_tgt;
    end
    time_idx = find(tms_all >= analysis_win(1) & tms_all <= analysis_win(2));
    if isempty(time_idx)
        error('analysis_win 溢出');
    end
    tms_win    = tms_all(time_idx);      % ms
    t_sec_full = tms_all/1000;           % s
    t_sec_win  = tms_win/1000;           % s
    n_timepoints = numel(time_idx);
    power_data   = zeros(n_trials, n_chans, n_freqs_eff, n_timepoints, 'single');

    fprintf('[%s] computing wavelet power (BOSC) ...\n', lock_type);

    % ---- ③ Power computation（trial × chan）----
    for ch = 1:n_chans
        for tr = 1:n_trials
            x = double(EEG.data(ch,:,tr));  % 1 × L
            B = zeros(length(freqs_eff), length(x));
            for fi = 1:length(freqs_eff)
                this_freq = freqs_eff(fi);
                this_cycle = num_cycles(fi);
                [B(fi,:), ~, ~] = BOSC_tf_power(x, this_freq, srate, this_cycle);
            end
            T_bosc = (1:length(x))/srate;
            F_bosc = freqs_eff;
            B_win = B(:, time_idx);     % [F × Twin]
            power_data(tr, ch, :, :) = single(B_win);
        end
    end

    % ---- ④ z-baseline（bootstrap）----
    z_power = zeros(size(power_data), 'single');

    switch lock_type
        case 'cue'
            % cue 用[-500，0]作为baseline
            bt = find(t_sec_win >= baseline_ref_s(1) & t_sec_win < baseline_ref_s(2));
            if isempty(bt)
                error('cue analysis_win 不包含baseline');
            end

            wm.powspctrm   = power_data;                   % [trial × chan × freq × time]
            base.powspctrm = power_data(:,:,:,bt); 

            [tfrz, mu_baseline, sigma_baseline] = zbaseline(wm, base, n_bs);
            z_power = single(tfrz.powspctrm);

        case 'target'
            % target：复用 cue baseline 的 μ/σ
            if isempty(mu_baseline) || isempty(sigma_baseline)
                Bstat = load(fullfile(data_dir, sprintf('%s_cue_baseline.mat', subj_id)), '-mat');
                mu_baseline    = Bstat.mu_baseline;
                sigma_baseline = Bstat.sigma_baseline;
            end

            z_power = zeros(size(power_data), 'like', power_data);
            for ch = 1:n_chans
                for f = 1:n_freqs_eff
                    mu = double(mu_baseline(ch,f));
                    sg = double(sigma_baseline(ch,f));
                    if ~isfinite(sg) || sg <= eps, sg = 1; end
                    z_power(:, ch, f, :) = (double(power_data(:, ch, f, :)) - mu) ./ sg;
                end
            end
            z_power = single(z_power);
    end


    % 输出结果
    chan_labels = {EEG.chanlocs.labels};
    meta = struct();
    meta.freqs          = freqs_eff;
    meta.method         = 'BOSC Morlet power';
    meta.wavenum        = num_cycles;
    meta.srate          = srate;
    meta.analysis_win   = analysis_win;
    if strcmp(lock_type,'cue')
        meta.baseline_win_s = [-0.5 0];
        meta.baseline_idx_rel = find(t_sec_win >= -0.5 & t_sec_win < 0);
    end
    
    out_file = fullfile(data_dir, sprintf('%s_%s_TF_zpower.mat', subj_id, lock_type));

    if strcmp(lock_type,'cue')
        save(out_file, 'z_power', 'freqs_eff', 'tms_win', 'mu_baseline', 'sigma_baseline', ...
                       'chan_labels', 'meta', '-v7.3');
        % 保存baseline
        save(fullfile(data_dir, sprintf('%s_cue_baseline.mat', subj_id)), ...
             'mu_baseline', 'sigma_baseline', '-v7.3');
    else
        save(out_file, 'z_power', 'freqs_eff', 'tms_win', ...
                       'chan_labels', 'meta', '-v7.3');
    end

    fprintf('✔ %s-locked TF (wavelet) saved -> %s\n', lock_type, out_file);
end

fprintf('\n波形功率分析完成！\n');

%% zbaseline function
% E. L. Johnson, PhD
% Copyright (c) 2017
% UC Berkeley
% eljohnson@berkeley.edu
function [tfrz, bmu, bsd] = zbaseline(data, baseline, npermutes)

if nargin < 3 || isempty(npermutes), npermutes = 1000; end

tfrz = data;
tfrz.powspctrm = zeros(size(tfrz.powspctrm), 'like', data.powspctrm);

ntrials = size(tfrz.powspctrm,1);
nelec   = size(tfrz.powspctrm,2);
nfreq   = size(tfrz.powspctrm,3);
ntimes  = size(tfrz.powspctrm,4);

bmu = zeros(nelec, nfreq, 'like', data.powspctrm);
bsd = zeros(nelec, nfreq, 'like', data.powspctrm);

for e = 1:nelec
    for f = 1:nfreq
        base = squeeze(baseline.powspctrm(:,e,f,:));
        base = base(:);
        base = base(isfinite(base));
        if isempty(base), base = 0; end

        basedist = zeros(1, npermutes);
        for z = 1:npermutes
            brand = randsample(base, ntrials, true);  % 每次抽 ntrials 个 → trial-平均口径
            basedist(z) = mean(brand);
        end

        m = mean(basedist);
        s = std(basedist);
        if ~isfinite(s) || s <= eps, s = 1; end

        % 记录 μ/σ（每电极×频率一个标量）
        bmu(e,f) = m;
        bsd(e,f) = s;
        bmean = repmat(m, [ntrials 1 1 ntimes]);
        bstd  = repmat(s, [ntrials 1 1 ntimes]);

        % z-score
        tfrz.powspctrm(:,e,f,:) = (data.powspctrm(:,e,f,:) - bmean) ./ bstd;
    end
end
end