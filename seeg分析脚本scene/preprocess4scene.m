%% ============================================================
%  Valence sEEG preprocessing + QC + TF (BOSC wavelet)
%  Output:
%   1) <subj>_rate_preproc.set
%   2) <subj>_valence_epoch.set
%   3) <subj>_valence_epoch_clean.set
%   4) <subj>_valence_QC.mat
%   5) <subj>_valence_TF_zpower.mat
%% ============================================================

%% ---------------- 基本参数 ----------------
subj_id = 'sub009';

% 只分析这些通道（留空 = 不裁）
%subj_channels = {'A1-Ref','A2-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref','POL E1','POL E2','POL E3','POL E6','POL E7'}; %sub001
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5','POL B3','POL B4','POL B1','POL B2','C4-Ref','C2-Ref','C3-Ref','POL D1','POL D2','POL D3','POL D4'}; %sub004
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL B1','POL B2','POL L7','POL L8','POL L9','POL L10','POL L13','POL L14'}; %sub005
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref','F5-Ref','POL H4','POL H5'}; %sub007
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5','POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'}; %sub008
subj_channels = {'A1-Ref','A2-Ref','POL A3','POL B1','POL B2','POL B3'}; %sub009

data_dir = pwd;
beh_dir  = '/Users/defanive/Desktop/Diploma/SEEG_behavior';

epoch_win = [-0.5 2];   % s

% Valence 映射（基于你之前的 0-5 六类）
% 0 -> nopress（不参与 valence TF）
% 1/2 -> negative
% 3 -> neutral
% 4/5 -> positive
valence_events_epoch = {'negative','neutral','positive'};  % 只 epoch 这三类

%% ============================================================
%% (0) 连续数据预处理
%% ============================================================
EEG = pop_resample(EEG, 1000);

EEG = pop_chanevent(EEG, 50,'oper','X>100000','edge','leading','edgelen',0);

EEG = pop_eegfiltnew(EEG, 'locutoff',1);
EEG = pop_eegfiltnew(EEG, 'hicutoff',200);
EEG = pop_eegfiltnew(EEG, 'locutoff',49,'hicutoff',51,'revfilt',1);

EEG = pop_clean_rawdata(EEG, ...
    'FlatlineCriterion',5,...
    'ChannelCriterion',0.8,...
    'LineNoiseCriterion',4,...
    'Highpass','off',...
    'BurstCriterion',20,...
    'WindowCriterion',0.25,...
    'BurstRejection','on');

EEG = pop_reref(EEG, []);
pop_saveset(EEG, 'filename', [subj_id '_rate_preproc.set']);
fprintf('✔ Saved: %s\n', [subj_id '_rate_preproc.set']);

%% ============================================================
%(1) 根据 scenematrix 生成事件（0-5 / 99）【正确策略版】
%- 200 ms 内去重：若已有事件在±200ms，跳过
%- 3000 ms 回看：若最近 3s 内出现过 type<=3 的事件，则当前事件强制 type=5
%- 否则按 scene_index 顺序取 scenematrix(scene_index, 5)
%- scene_index > 120 的事件全部置 99
%============================================================

S = load(fullfile(beh_dir, [subj_id '_scene.mat']));  % 例如 sub001_scene.mat
if isfield(S,'scenematrix')
    scenematrix = S.scenematrix;
elseif isfield(S,'ratingmatrix')
    scenematrix = S.ratingmatrix;   % 兜底：有的人把它也叫 ratingmatrix
else
    error('scene.mat 里找不到变量 scenematrix / ratingmatrix。');
end

latencies = [EEG.event.latency];
n_events  = numel(latencies);

newevent    = [];   % N×2: [type, latency]
scene_index = 0;

for i = 1:n_events
    current_latency = latencies(i);

    % (A) 200ms 去重：已有事件在±200ms就跳过
    if ~isempty(newevent) && any(abs(newevent(:,2) - current_latency) <= 200)
        continue;
    end

    % (B) 3000ms 回看：最近3s内若已有 type<=3 的事件，则强制 type=5
    recent_window_start = current_latency - 3000;
    if ~isempty(newevent) && any(newevent(:,2) >= recent_window_start & ...
                                 newevent(:,2) <  current_latency   & ...
                                 newevent(:,1) <= 3)
        event_type = 5;
    else
        % 否则进入下一条 scene
        scene_index = scene_index + 1;
        if scene_index <= 120
            event_type = scenematrix(scene_index, 5);
        else
            event_type = 99;
        end
    end

    % (C) 记录事件：超过120一律99（跟你的原策略一致）
    if scene_index <= 120
        newevent = [newevent; event_type, current_latency];
    else
        newevent = [newevent; 99, current_latency];
    end
end

% 导入事件（覆盖旧事件 or 追加：你之前用 append='no'，保持一致）
EEG = pop_importevent(EEG,'append','no','event',newevent,...
    'fields',{'type','latency'},'timeunit',NaN,'optimalign','off');

EEG = eeg_checkset(EEG,'eventconsistency');

fprintf('✔ Imported events: %d (scene_index=%d, last type=%d)\n', ...
    size(newevent,1), scene_index, newevent(end,1));

%% ============================================================
%% (2) 合并 6 类事件 → 3 类 valence（negative/neutral/positive）并检查窗长
%%     原策略：保留原事件 + 追加同latency的新事件；窗长不够则跳过
%% ============================================================

toStr = @(x) string(x);
newEvents = EEG.event;

pre_samp  = round(abs(epoch_win(1)) * EEG.srate);
post_samp = round(epoch_win(2)       * EEG.srate);

addCount  = 0;
skipCount = 0;

for i = 1:numel(EEG.event)
    etype = toStr(EEG.event(i).type);

    % 跳过 boundary
    if etype == "boundary"
        continue;
    end

    % 只接受 0–5
    if ~ismember(etype, ["0","1","2","3","4","5"])
        continue;
    end

    % ===== 映射：0不进epoch；1/2=negative；3=neutral；4/5=positive =====
    if etype == "1"
        lab = "negative";
    elseif etype == "2"
        lab = "neutral";
    elseif etype == "3"
        lab = "positive";
    else
        lab = "nopress";   % 4/5
    end

    % ===== 窗长检查：能否切 epoch_win =====
    lat = EEG.event(i).latency; % 样本点（可小数）
    if (lat - pre_samp < 1) || (lat + post_samp > EEG.pnts)
        skipCount = skipCount + 1;
        continue;
    end

    % ===== 只追加 negative/neutral/positive（nopress不追加）=====
    if ismember(lab, ["negative","neutral","positive"])
        e2         = EEG.event(i);     % 用原事件做模板
        e2.type    = char(lab);        % 写成 char，兼容 EEGLAB
        e2.latency = EEG.event(i).latency;

        newEvents(end+1) = e2; %#ok<SAGROW>
        addCount = addCount + 1;
    end
end

EEG.event = newEvents;

% 事件一致性 & 按 latency 排序（强烈建议，避免 epoch 时乱序）
EEG = eeg_checkset(EEG, 'eventconsistency');
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');

fprintf('✔ Added valence events: %d (neg/neu/pos). Skipped (window): %d\n', addCount, skipCount);

%% ============================================================
%% (3) Epoch（negative/neutral/positive）
%% ============================================================
EEG = pop_epoch(EEG, {'negative','neutral','positive'}, epoch_win);
EEG.setname = [subj_id '_valence_epoch'];
pop_saveset(EEG, 'filename', [subj_id '_valence_epoch.set']);
fprintf('✔ Saved: %s\n', [subj_id '_valence_epoch.set']);

%% ============================================================
%% (4) 通道选择（可选）
%% ============================================================
if exist('subj_channels','var') && ~isempty(subj_channels)
    have_labels = {EEG.chanlocs.labels};
    keep = intersect(subj_channels, have_labels, 'stable');
    if isempty(keep)
        warning('subj_channels 全部缺失：不做通道裁剪。');
    else
        miss = setdiff(subj_channels, keep);
        if ~isempty(miss)
            warning('以下指定通道缺失，将忽略：%s', strjoin(miss, ', '));
        end
        EEG = pop_select(EEG,'channel',keep);
        fprintf('✔ Channel selection: kept %d channels\n', numel(keep));
    end
end

%% ============================================================
%% (5) Trial QC（保留：鲁棒策略 + 阈值策略）
%% ============================================================

tms      = EEG.times;
n_tr     = EEG.trials;
n_ch     = EEG.nbchan;
ch_names = {EEG.chanlocs.labels};

% ---- 鲁棒策略参数（与你原来一致）----
baseline_win  = [-500 0];  % ms
post_win      = [0 1000];  % ms
thr_z         = 4;
vote_M_robust = 5;

% ---- 阈值策略（abs + P2P 3σ）----
abs_threshold = 200;   % uV
sigma_p2p     = 3;
vote_M_sigma  = 3;

eps_small = 1e-12;

base_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
post_idx = find(tms >= post_win(1)     & tms <= post_win(2));
if isempty(base_idx) || isempty(post_idx)
    error('baseline_win 或 post_win 超出 epoch 时间范围，请调整。');
end

% 条件识别：neg/neu/pos
is_neg = false(n_tr,1);
is_neu = false(n_tr,1);
is_pos = false(n_tr,1);
for k = 1:n_tr
    et = EEG.epoch(k).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_neg(k) = any(types == "negative");
    is_neu(k) = any(types == "neutral");
    is_pos(k) = any(types == "positive");
end

% ========== A) 鲁棒策略：RMS log比值 + post窗P2P，按条件 MAD-Z ==========
flag_rms = false(n_tr, n_ch);
flag_p2p = false(n_tr, n_ch);

for ch = 1:n_ch
    X  = squeeze(EEG.data(ch, :, :)).';     % [trial x time]
    xb = sqrt(mean(X(:, base_idx).^2, 2));
    xp = sqrt(mean(X(:, post_idx).^2,  2));
    r  = log( xp ./ max(xb, eps_small) );
    p2p_post = max(X(:, post_idx),[],2) - min(X(:, post_idx),[],2);

    % local helper (inline)
    do_robust = @(mask, vec) deal( ...
        0.6745*(vec(mask)-median(vec(mask)))./max(mad(vec(mask),1),eps_small), ...
        find(mask) );

    if any(is_neg)
        [z_r, idx] = do_robust(is_neg, r);
        flag_rms(idx,ch) = z_r > thr_z;

        [z_p, idx] = do_robust(is_neg, p2p_post);
        flag_p2p(idx,ch) = z_p > thr_z;
    end
    if any(is_neu)
        [z_r, idx] = do_robust(is_neu, r);
        flag_rms(idx,ch) = z_r > thr_z;

        [z_p, idx] = do_robust(is_neu, p2p_post);
        flag_p2p(idx,ch) = z_p > thr_z;
    end
    if any(is_pos)
        [z_r, idx] = do_robust(is_pos, r);
        flag_rms(idx,ch) = z_r > thr_z;

        [z_p, idx] = do_robust(is_pos, p2p_post);
        flag_p2p(idx,ch) = z_p > thr_z;
    end
end

flag_robust = flag_rms | flag_p2p;

% ========== B) 阈值策略：abs阈值 + 全窗P2P 3σ（neg/pos 分开；neutral 可选） ==========
flag_abs   = false(n_tr, n_ch);
flag_p2p3s = false(n_tr, n_ch);

for ch = 1:n_ch
    X = squeeze(EEG.data(ch, :, :)).';  % full epoch window
    flag_abs(:, ch) = any(abs(X) >= abs_threshold, 2);

    p2p_full = max(X, [], 2) - min(X, [], 2);

    if any(is_neg)
        p = p2p_full(is_neg);
        thr = mean(p) + sigma_p2p * max(std(p), eps_small);
        idx = find(is_neg);
        flag_p2p3s(idx, ch) = p > thr;
    end
    if any(is_pos)
        p = p2p_full(is_pos);
        thr = mean(p) + sigma_p2p * max(std(p), eps_small);
        idx = find(is_pos);
        flag_p2p3s(idx, ch) = p > thr;
    end

    % 如果你也想 neutral 单独算 3σ，把下面注释打开：
    % if any(is_neu)
    %     p = p2p_full(is_neu);
    %     thr = mean(p) + sigma_p2p * max(std(p), eps_small);
    %     idx = find(is_neu);
    %     flag_p2p3s(idx, ch) = p > thr;
    % end
end

flag_sigma = flag_abs | flag_p2p3s;

% ========== C) 合并：分别投票 + 取并集 ==========
n_flag_robust = sum(flag_robust, 2);
n_flag_sigma  = sum(flag_sigma,  2);

reject_robust = n_flag_robust >= vote_M_robust;
reject_sigma  = n_flag_sigma  >= vote_M_sigma;

reject_mask = reject_robust | reject_sigma;
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);

fprintf('\n==== QC Summary (%s valence epoch) ====\n', subj_id);
fprintf('Trials total: %d\n', n_tr);
fprintf('Robust: thr_z=%.2f, vote_M=%d -> reject %d (%.2f%%)\n', ...
    thr_z, vote_M_robust, sum(reject_robust), 100*sum(reject_robust)/n_tr);
fprintf('Sigma : abs=%g uV, 3sd=%g, vote_M=%d -> reject %d (%.2f%%)\n', ...
    abs_threshold, sigma_p2p, vote_M_sigma, sum(reject_sigma), 100*sum(reject_sigma)/n_tr);
fprintf('Union -> reject %d (%.2f%%)\n', numel(reject_idx), 100*numel(reject_idx)/n_tr);

% 保存 QC
QC = struct();
QC.subj_id = subj_id;
QC.epoch_win = epoch_win;
QC.baseline_win = baseline_win;
QC.post_win = post_win;

QC.thr_z = thr_z;
QC.vote_M_robust = vote_M_robust;

QC.abs_threshold = abs_threshold;
QC.sigma_p2p = sigma_p2p;
QC.vote_M_sigma = vote_M_sigma;

QC.keep_idx = keep_idx;
QC.reject_idx = reject_idx;
QC.reject_mask = reject_mask;

QC.is_neg = is_neg; QC.is_neu = is_neu; QC.is_pos = is_pos;

QC.flag_rms = flag_rms;
QC.flag_p2p = flag_p2p;
QC.flag_abs = flag_abs;
QC.flag_p2p3s = flag_p2p3s;
QC.flag_robust = flag_robust;
QC.flag_sigma  = flag_sigma;

save(fullfile(data_dir, [subj_id '_valence_QC.mat']), 'QC');
fprintf('✔ Saved: %s\n', [subj_id '_valence_QC.mat']);

%% ============================================================
%% (6) 保存 clean epoch
%% ============================================================
EEG_clean = pop_select(EEG,'trial',keep_idx);
EEG_clean.setname = [subj_id '_valence_epoch_clean'];
pop_saveset(EEG_clean,'filename',[subj_id '_valence_epoch_clean.set']);
fprintf('✔ Saved: %s\n', [subj_id '_valence_epoch_clean.set']);

%% ============================================================
%% (7) Time-Frequency (BOSC Morlet) -> <subj>_valence_TF_zpower.mat
%% ============================================================

% ---- TF 参数 ----
lock_name = 'valence';

freqs    = logspace(log10(2), log10(120), 24);  % 2-120 Hz, 24 log points
num_cycles = logspace(log10(3), log10(12), numel(freqs));

n_bs   = 1000;
ds_ms  = 50;

baseline_tf = [-500 0];   % ms
analysis_tf  = [0 2000];  % ms

% 重新用 clean 数据跑 TF（更稳）
EEG = EEG_clean;

srate    = EEG.srate;
n_trials = EEG.trials;
n_chans  = EEG.nbchan;
tms      = EEG.times;
chan_labels = {EEG.chanlocs.labels};

% 条件 mask（neg/neu/pos）
is_neg = false(n_trials,1);
is_neu = false(n_trials,1);
is_pos = false(n_trials,1);
for tr = 1:n_trials
    et = EEG.epoch(tr).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_neg(tr) = any(types == "negative");
    is_neu(tr) = any(types == "neutral");
    is_pos(tr) = any(types == "positive");
end
cond_labels = {'neg','neu','pos'};
cond_mask   = {is_neg, is_neu, is_pos};

% 时间索引
time_idx     = find(tms >= analysis_tf(1)  & tms <= analysis_tf(2));
baseline_idx = find(tms >= baseline_tf(1) & tms <= baseline_tf(2));
if isempty(time_idx) || isempty(baseline_idx)
    error('TF baseline/analysis window 超出 epoch 时间范围。');
end

% Nyquist 保护
nyq = srate/2;
keep_f = freqs < nyq - 1e-6;
if any(~keep_f)
    warning('freqs 超 Nyquist 已剔除：%d -> %d', numel(freqs), nnz(keep_f));
end
freqs = freqs(keep_f);
num_cycles = num_cycles(keep_f);
n_freqs = numel(freqs);

n_timepoints = numel(time_idx);
n_basepoints = numel(baseline_idx);

power_data      = zeros(n_trials, n_chans, n_freqs, n_timepoints, 'single');
base_power_data = zeros(n_trials, n_chans, n_freqs, n_basepoints, 'single');

fprintf('[%s] BOSC wavelet power...\n', lock_name);

for tr = 1:n_trials
    if mod(tr, 10) == 0, fprintf('  trial %d/%d\n', tr, n_trials); end
    for ch = 1:n_chans
        x = double(EEG.data(ch,:,tr));  % 1 x T
        T = numel(x);

        B = zeros(n_freqs, T);
        for fi = 1:n_freqs
            [B(fi,:), ~, ~] = BOSC_tf_power(x, freqs(fi), srate, num_cycles(fi));
        end

        power_data(tr, ch, :, :)      = single(B(:, time_idx));
        base_power_data(tr, ch, :, :) = single(B(:, baseline_idx));
    end
end

% ---- bootstrap baseline z ----
z_power        = zeros(size(power_data), 'single');
mu_baseline    = zeros(n_chans, n_freqs, 'single');
sigma_baseline = zeros(n_chans, n_freqs, 'single');

for ch = 1:n_chans
    for f = 1:n_freqs
        base_vals = squeeze(base_power_data(:, ch, f, :));
        base_all  = base_vals(:);

        null_distr = zeros(n_bs,1);
        for b = 1:n_bs
            sample = randsample(base_all, n_trials, true);
            null_distr(b) = mean(sample);
        end
        mu = mean(null_distr);
        sg = std(null_distr);

        mu_baseline(ch,f)    = mu;
        sigma_baseline(ch,f) = max(sg, eps);

        z_power(:, ch, f, :) = (power_data(:, ch, f, :) - mu) ./ sigma_baseline(ch,f);
    end
end

% ---- downsample time ----
dt        = mean(diff(tms));             % ms/sample
ds_factor = max(1, round(ds_ms / dt));
sel_idx   = 1:ds_factor:n_timepoints;

z_power_ds = z_power(:, :, :, sel_idx);
tms_ds     = tms(time_idx);
tms_ds     = tms_ds(sel_idx);

% ---- condition mean ----
n_cond = 3;
cond_mean_z = nan(n_cond, n_chans, n_freqs, numel(sel_idx), 'single');
cond_n      = zeros(n_cond,1);

for c = 1:n_cond
    mask = cond_mask{c};
    if any(mask)
        cond_mean_z(c, :, :, :) = squeeze(mean(z_power_ds(mask, :, :, :), 1, 'omitnan'));
        cond_n(c) = sum(mask);
    end
end

% ---- save ----
out_file = fullfile(data_dir, sprintf('%s_%s_scene_TF_zpower.mat', subj_id, lock_name));
save(out_file, ...
    'z_power_ds', 'freqs', 'tms_ds', 'mu_baseline', 'sigma_baseline', ...
    'chan_labels', 'cond_labels', 'cond_mean_z', 'cond_n', ...
    'is_neg','is_neu','is_pos', '-v7.3');

fprintf('✔ Saved TF: %s\n', out_file);
fprintf('\n✔ Pipeline finished for %s\n', subj_id);
