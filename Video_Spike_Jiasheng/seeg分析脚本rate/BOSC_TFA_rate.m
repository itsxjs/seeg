%% ===== Valence-locked Time-Frequency Analysis (Hilbert) =====
% 依赖：EEGLAB 已载入；已存在 <subj_id>_4bin_epoch_clean.set
% 目标：对 dislike / like 两类事件的 epoch 做 TFA
% 1) 逐频带带通 + Hilbert -> 功率
% 2) 以 [-500,0]ms 基线（全trial合并）做 bootstrap μ/σ
% 3) 全trial z-score（同一参考系，便于条件可比）
% 4) 50 ms 下采样
% 5) 保存 trial 级与条件平均的时频 z 值

%% ---- 参数 ----
subj_id   = 'sub008';                       % 按需修改
data_dir  = pwd;                            % .set 所在目录
in_files  = { ...
    sprintf('%s_4bin_epoch_clean.set', subj_id), ...  % 优先使用 QC 后
    sprintf('%s_4bin_epoch.set',        subj_id)  ... % 兜底
};
lock_name = 'valence';                      % 标记用（输出文件名用）

% 频率轴
freqs   = logspace(log10(2), log10(120), 24);  % 24 个对数间隔频点
n_bs    = 1000;                             % bootstrap 次数
ds_ms   = 50;                               % 下采样到 50 ms
target_ms = 4000;                           % 零填充统一长度（ms）

% 时间窗（相对事件）
baseline_win = [-500 0];                    % 基线
analysis_win = [0 2000];                    % 分析窗（4bin epoch [-0.5 2] 内）

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

%% ---- 条件标签（从 epoch 的事件类型中识别 dislike / like）----
is_dislike = false(n_trials,1);
is_like    = false(n_trials,1);

for tr = 1:n_trials
    et = EEG.epoch(tr).eventtype;
    if iscell(et)
        types = string(et);
    else
        types = string({et});
    end
    % 这里假设前一步脚本已把事件 type 映射为 'dislike' / 'like'
    is_dislike(tr) = any(types == "dislike");
    is_like(tr)    = any(types == "like");
end

if ~(any(is_dislike) || any(is_like))
    warning('未识别到 dislike/like 事件，请检查事件标注。');
end

cond_labels = {'dislike','like'};
cond_mask   = {is_dislike, is_like};

%% ---- 时间索引 ----
time_idx     = find(tms >= analysis_win(1) & tms <= analysis_win(2));
baseline_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
if isempty(time_idx) || isempty(baseline_idx)
    error('baseline_win 或 analysis_win 超出 epoch 时间范围，请调整。');
end
n_timepoints  = numel(time_idx);
n_basepoints  = numel(baseline_idx);
target_points = round(target_ms / 1000 * srate);  % 统一零填充点数

%% ---- Step 1': Morlet wavelet power (BOSC_tf_power) ----
n_freqs = numel(freqs);

% Nyquist保护
nyq = srate/2;
freqs_eff = freqs(freqs < nyq - 1e-6);
if numel(freqs_eff) < numel(freqs)
    warning('freqs包含超过Nyquist的频点，已剔除：原%d -> 现%d', numel(freqs), numel(freqs_eff));
end
freqs = freqs_eff;
n_freqs = numel(freqs);

% 给每个频点分配 Morlet cycles（可调）
num_cycles = logspace(log10(3), log10(12), n_freqs);

n_timepoints = numel(time_idx);
n_basepoints = numel(baseline_idx);

power_data      = zeros(n_trials, n_chans, n_freqs, n_timepoints, 'single');
base_power_data = zeros(n_trials, n_chans, n_freqs, n_basepoints, 'single');

fprintf('[%s] computing wavelet power (BOSC_tf_power) ...\n', lock_name);

for tr = 1:n_trials
    if mod(tr, 10) == 0
        fprintf('  trial %d / %d\n', tr, n_trials);
    end

    for ch = 1:n_chans
        x = double(EEG.data(ch,:,tr));      % 1 × L
        L = numel(x);

        % 计算每个频点的功率：B(f, t)
        B = zeros(n_freqs, L);             % [F × T]
        for fi = 1:n_freqs
            this_freq  = freqs(fi);
            this_cycle = num_cycles(fi);
            % BOSC_tf_power 输出通常就是功率(或幅度平方)，与你的power_data语义一致
            [B(fi,:), ~, ~] = BOSC_tf_power(x, this_freq, srate, this_cycle);
        end

        % 截出分析窗与基线窗
        B_win  = B(:, time_idx);           % [F × Twin]
        B_base = B(:, baseline_idx);       % [F × Tbase]

        % 存成 [trial × chan × freq × time]
        power_data(tr, ch, :, :)      = single(B_win);
        base_power_data(tr, ch, :, :) = single(B_base);
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

%% ---- Step 4: 条件平均（dislike / like）----
% 输出 cond_mean_z: [cond x chan x freq x time]
n_cond = 2;
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
out_file = fullfile(data_dir, sprintf('%s_%s_BOSC_TF_zpower.mat', subj_id, lock_name));
save(out_file, ...
    'z_power_ds', 'freqs', 'tms_ds', 'mu_baseline', 'sigma_baseline', ...
    'chan_labels', 'cond_labels', 'cond_mean_z', 'cond_n', ...
    'is_dislike','is_like', '-v7.3');

fprintf('✔ %s-locked TF analysis saved to: %s\n', lock_name, out_file);
