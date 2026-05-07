%% ===== Valence-locked Time-Frequency Analysis (Hilbert) =====
% 依赖：EEGLAB 已载入；已存在 <subj_id>_valence_epoch_clean.set
% 目标：对 negative / neutral / positive 的 valence-locked epoch 做 TFA
% 1) 逐频带带通 + Hilbert -> 功率
% 2) 以 [-500,0]ms 基线（全trial合并）做 bootstrap μ/σ
% 3) 全trial z-score（同一参考系，便于条件可比）
% 4) 50 ms 下采样
% 5) 保存 trial 级与条件平均的时频 z 值

%% ---- 参数 ----
subj_id   = 'sub009';                      % 按需修改
data_dir  = pwd;                            % .set 所在目录
in_files  = { ...
    sprintf('%s_valence_epoch_clean.set', subj_id), ...
    sprintf('%s_valence_epoch.set', subj_id) ... % 兜底
};
lock_name = 'valence';                      % 标记用

% 频率轴
freqs   = logspace(log10(1), log10(192), 24);  % 24 个对数间隔频点
n_bs    = 1000;                             % bootstrap 次数
ds_ms   = 50;                               % 下采样到 50 ms
target_ms = 4000;                           % 零填充统一长度（ms）

% 时间窗（相对事件）
baseline_win = [-500 0];                    % 基线
analysis_win = [0 2000];                    % 分析窗（valence epoch [-0.5 2] 内）

%% ---- 载入数据（优先 clean）----
EEG = [];
for k = 1:numel(in_files)
    fn = fullfile(data_dir, in_files{k});
    if exist(fn, 'file')
        EEG = pop_loadset('filename', in_files{k}, 'filepath', data_dir);
        fprintf('✔ Loaded: %s\n', in_files{k});
        break;
    end
end
if isempty(EEG)
    error('找不到 %s 或 %s，请确认路径与文件名。', in_files{1}, in_files{2});
end

srate    = EEG.srate;
n_trials = EEG.trials;
n_chans  = EEG.nbchan;
tms      = EEG.times;

% 条件标签（从 epoch 的事件类型中识别）
is_neg = false(n_trials,1);
is_neu = false(n_trials,1);
is_pos = false(n_trials,1);
for tr = 1:n_trials
    et = EEG.epoch(tr).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_neg(tr) = any(strcmp(types,'negative'));
    is_neu(tr) = any(strcmp(types,'neutral'));
    is_pos(tr) = any(strcmp(types,'positive'));
end
if ~(any(is_neg) || any(is_neu) || any(is_pos))
    warning('未识别到 negative/neutral/positive 事件，请检查事件标注。');
end
cond_labels = {'neg','neu','pos'};
cond_mask   = {is_neg, is_neu, is_pos};

% 时间索引
time_idx    = find(tms >= analysis_win(1) & tms <= analysis_win(2));
baseline_idx= find(tms >= baseline_win(1) & tms <= baseline_win(2));
if isempty(time_idx) || isempty(baseline_idx)
    error('baseline_win 或 analysis_win 超出 epoch 时间范围，请调整。');
end
n_timepoints = numel(time_idx);

% 统一零填充点数
target_points = round(target_ms / 1000 * srate);

%% ---- Step 1: 逐频带带通 + Hilbert 功率（同时保存baseline窗）----
n_freqs = numel(freqs);
n_timepoints = numel(time_idx);
n_basepoints = numel(baseline_idx);

power_data      = zeros(n_trials, n_chans, n_freqs, n_timepoints, 'single');
base_power_data = zeros(n_trials, n_chans, n_freqs, n_basepoints, 'single');

for f = 1:n_freqs
    f0 = freqs(f);
    f_low  = f0 / sqrt(2);
    f_high = f0 * sqrt(2);
    filt_order = round(3 * srate / max(f_low, 0.1));
    filt_order = filt_order + mod(filt_order, 2); % 偶数阶

    fprintf('[%s] Filtering %.2f Hz (%.2f–%.2f Hz), order=%d ...\n', ...
        lock_name, f0, f_low, f_high, filt_order);

    EEG_f = pop_eegfiltnew(EEG, f_low, f_high, filt_order, 0, [], 0);

    for tr = 1:n_trials
        for ch = 1:n_chans
            signal = double(EEG_f.data(ch,:,tr));
            L = numel(signal);

            % 零填充，减少边缘效应
            if L < target_points
                pad_total = target_points - L;
                pad_left  = floor(pad_total/2);
                pad_right = ceil(pad_total/2);
                sig_pad   = [zeros(1,pad_left), signal, zeros(1,pad_right)];
            else
                sig_pad   = signal;
                pad_left  = 0;
            end

            h    = hilbert(sig_pad);
            amp2 = abs(h).^2;

            % 去补零，回到原 epoch 长度
            amp2 = amp2(pad_left+1 : pad_left+L);

            % 分别截出“分析窗”和“基线窗”的功率
            power_data(tr, ch, f, :)      = amp2(time_idx);
            base_power_data(tr, ch, f, :) = amp2(baseline_idx);
        end
    end
end

%% ---- Step 2: 基于 baseline 的 bootstrap z-score（通道×频率）----
z_power        = zeros(size(power_data), 'single');
mu_baseline    = zeros(n_chans, n_freqs, 'single');
sigma_baseline = zeros(n_chans, n_freqs, 'single');

for ch = 1:n_chans
    for f = 1:n_freqs
        % 直接用预先保存好的 baseline 功率
        base_vals = squeeze(base_power_data(:, ch, f, :));   % [trial x base_time]
        base_all  = base_vals(:);

        % bootstrap 试次均值的零分布
        null_distr = zeros(n_bs,1);
        for b = 1:n_bs
            sample = randsample(base_all, n_trials, true);
            null_distr(b) = mean(sample);
        end
        mu = mean(null_distr);
        sg = std(null_distr);

        mu_baseline(ch,f)    = mu;
        sigma_baseline(ch,f) = max(sg, eps);

        % 对分析窗的功率做 z-score
        z_power(:, ch, f, :) = (power_data(:, ch, f, :) - mu) ./ sigma_baseline(ch,f);
    end
end


%% ---- Step 3: 时间下采样（50 ms）----
dt        = mean(diff(tms));             % ms / sample
ds_factor = max(1, round(ds_ms / dt));   % 取整
sel_idx   = 1:ds_factor:n_timepoints;

z_power_ds = z_power(:, :, :, sel_idx);
tms_ds     = tms(time_idx);
tms_ds     = tms_ds(sel_idx);
chan_labels = {EEG.chanlocs.labels};

%% ---- Step 4: 条件平均（可视化友好）----
% 输出 cond_mean_z: [cond x chan x freq x time]
n_cond = 3;
cond_mean_z = nan(n_cond, n_chans, numel(freqs), numel(sel_idx), 'single');
cond_n      = zeros(n_cond,1);

for c = 1:n_cond
    mask = cond_mask{c};
    if any(mask)
        cond_mean_z(c, :, :, :) = squeeze(mean(z_power_ds(mask, :, :, :), 1, 'omitnan'));
        cond_n(c) = sum(mask);
    end
end

%% ---- Step 5: 保存结果 ----
out_file = fullfile(data_dir, sprintf('%s_%s_scene_TF_zpower.mat', subj_id, lock_name));
save(out_file, ...
    'z_power_ds', 'freqs', 'tms_ds', 'mu_baseline', 'sigma_baseline', ...
    'chan_labels', 'cond_labels', 'cond_mean_z', 'cond_n', ...
    'is_neg','is_neu','is_pos', '-v7.3');

fprintf('✔ %s-locked TF analysis saved to: %s\n', lock_name, out_file);

