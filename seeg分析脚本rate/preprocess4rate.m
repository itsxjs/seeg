%% ============================================================
%  Valence sEEG preprocessing + QC + TF (BOSC wavelet)
% ============================================================

%% ---------------- 基本参数 ----------------
subj_id = 'sub001';

% 只分析这些通道（留空 = 不裁）
subj_channels = {'A1-Ref','A2-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref','POL E1','POL E2','POL E3','POL E6','POL E7'}; %sub001
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5','POL B3','POL B4','POL B1','POL B2','C4-Ref','C2-Ref','C3-Ref','POL D1','POL D2','POL D3','POL D4'}; %sub004
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL B1','POL B2','POL L7','POL L8','POL L9','POL L10','POL L13','POL L14'}; %sub005
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref','F5-Ref','POL H4','POL H5'}; %sub007
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5','POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'}; %sub008
%subj_channels = {'A1-Ref','A2-Ref','POL A3','POL B1','POL B2','POL B3'}; %sub009


data_dir = pwd;
beh_dir  = '/Users/defanive/Desktop/Diploma/SEEG_behavior';

epoch_win = [-0.5 2];   % s

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

%% ============================================================
%% (1) 根据 ratingmatrix 生成事件
%% ============================================================

ratingmatrix = load(fullfile(beh_dir, [subj_id '_ratingmatrix.mat']));
ratingmatrix = ratingmatrix.ratingmatrix;

latencies = [EEG.event.latency];
newevent = [];
rate_index = 0;

for i = 1:numel(latencies)
    if ~isempty(newevent) && any(abs(newevent(:,2) - latencies(i)) <= 200)
        continue;
    end
    rate_index = rate_index + 1;
    if rate_index <= size(ratingmatrix,1)
        ev_type = ratingmatrix(rate_index,3);
    else
        ev_type = 99;
    end
    newevent = [newevent; ev_type, latencies(i)];
end

EEG = pop_importevent(EEG,'append','no','event',newevent,...
    'fields',{'type','latency'},'timeunit',NaN);

EEG = eeg_checkset(EEG,'eventconsistency');

%% ============================================================
%% (2) 合并 6 类事件 → 4 类 valence
%% ============================================================

toStr = @(x) string(x);
newEvents = EEG.event;
pre_samp  = round(abs(epoch_win(1)) * EEG.srate);
post_samp = round(epoch_win(2)       * EEG.srate);

for i = 1:numel(EEG.event)
    et = toStr(EEG.event(i).type);
    if et == "boundary", continue; end
    if ~ismember(et, ["0","1","2","3","4","5"]), continue; end

    if et=="0", lab="nopress";
    elseif et=="1"||et=="2", lab="dislike";
    elseif et=="3", lab="neutral";
    else, lab="like";
    end

    lat = EEG.event(i).latency;
    if lat-pre_samp<1 || lat+post_samp>EEG.pnts, continue; end

    e2 = EEG.event(i);
    e2.type = lab;
    newEvents(end+1) = e2;
end

EEG.event = newEvents;
EEG = eeg_checkset(EEG,'eventconsistency');

%% ============================================================
%% (3) Epoch
%% ============================================================

EEG = pop_epoch(EEG, {'nopress','dislike','neutral','like'}, epoch_win);
EEG.setname = [subj_id '_4bin_epoch'];
pop_saveset(EEG, 'filename', [subj_id '_4bin_epoch.set']);

%% ============================================================
%% (4) 通道选择（可选）
%% ============================================================

if ~isempty(subj_channels)
    keep = intersect(subj_channels, {EEG.chanlocs.labels}, 'stable');
    EEG = pop_select(EEG,'channel',keep);
end

%% ============================================================
%% (5) Trial QC（鲁棒 + 阈值策略）
%% ============================================================


% 基本参数
tms      = EEG.times;
fs       = EEG.srate;
n_tr     = EEG.trials;
n_ch     = EEG.nbchan;
ch_names = {EEG.chanlocs.labels};

% QC 参数（原策略：鲁棒Z）
baseline_win = [-500 0];  % ms
post_win     = [0 1000];  % ms
thr_z        = 4;         % 单侧阈值（鲁棒Z）
vote_M_robust = 5;        % 鲁棒策略投票：≥M个通道命中 -> 剔除

% 新增策略：abs阈值 + P2P 3σ（like/dislike分开）
abs_threshold = 200;      % uV：任一点 |ERP|>=200
sigma_p2p     = 3;        % mean + 3*std
vote_M_sigma  = 3;        % 阈值策略投票：建议更敏感（你也可设成 5 跟robust一致）

eps_small    = 1e-12;

% 时间索引检查
base_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
post_idx = find(tms >= post_win(1)     & tms <= post_win(2));
if isempty(base_idx) || isempty(post_idx)
    error('baseline_win 或 post_win 超出 epoch 时间范围，请调整。');
end

% 条件识别（按 epoch 的事件类型；注意一个 epoch 里可能有多个 eventtype）
is_nopress = false(n_tr,1);
is_dislike = false(n_tr,1);
is_neutral = false(n_tr,1);
is_like    = false(n_tr,1);

for k = 1:n_tr
    et = EEG.epoch(k).eventtype;
    if iscell(et)
        types = string(et);
    else
        types = string({et});
    end
    is_nopress(k) = any(types == "nopress");
    is_dislike(k) = any(types == "dislike");
    is_neutral(k) = any(types == "neutral");
    is_like(k)    = any(types == "like");
end

% ========== A) 原策略：RMS log比值 + post窗P2P，按条件鲁棒Z ==========
flag_rms = false(n_tr, n_ch);
flag_p2p = false(n_tr, n_ch);

for ch = 1:n_ch
    X  = squeeze(EEG.data(ch, :, :)).';     % [n_tr x n_time]
    xb = sqrt(mean(X(:, base_idx).^2, 2));  % baseline RMS
    xp = sqrt(mean(X(:, post_idx).^2,  2)); % post RMS
    r  = log( xp ./ max(xb, eps_small) );   % log 比值
    p2p_post = max(X(:, post_idx),[],2) - min(X(:, post_idx),[],2);

    % helper：给某个条件做robust Z 并写入 flag
    % nopress
    if any(is_nopress)
        r_   = r(is_nopress);
        p_   = p2p_post(is_nopress);

        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_nopress);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % dislike
    if any(is_dislike)
        r_   = r(is_dislike);
        p_   = p2p_post(is_dislike);

        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_dislike);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % neutral
    if any(is_neutral)
        r_   = r(is_neutral);
        p_   = p2p_post(is_neutral);

        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_neutral);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % like
    if any(is_like)
        r_   = r(is_like);
        p_   = p2p_post(is_like);

        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_like);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end
end

% 鲁棒策略：trial×chan 命中矩阵
flag_robust = flag_rms | flag_p2p;

% ========== B) 新增策略：abs阈值 + 全窗P2P 3σ（like/dislike分开） ==========
flag_abs   = false(n_tr, n_ch);   % any(|x|>=200) in full epoch
flag_p2p3s = false(n_tr, n_ch);   % P2P(full epoch) > mean+3std within like/dislike

for ch = 1:n_ch
    X = squeeze(EEG.data(ch, :, :)).';     % [n_tr x n_time] 全epoch窗

    % (1) abs阈值（全窗）
    flag_abs(:, ch) = any(abs(X) >= abs_threshold, 2);

    % (2) 全窗 P2P
    p2p_full = max(X, [], 2) - min(X, [], 2);

    % like 单独阈值
    if any(is_like)
        p_like = p2p_full(is_like);
        thr_like = mean(p_like) + sigma_p2p * max(std(p_like), eps_small);
        idx = find(is_like);
        flag_p2p3s(idx, ch) = p_like > thr_like;
    end

    % dislike 单独阈值
    if any(is_dislike)
        p_dis = p2p_full(is_dislike);
        thr_dis = mean(p_dis) + sigma_p2p * max(std(p_dis), eps_small);
        idx = find(is_dislike);
        flag_p2p3s(idx, ch) = p_dis > thr_dis;
    end

    % 如你希望 neutral / nopress 也做 3σ，可在此按同样方式添加
end

flag_sigma = flag_abs | flag_p2p3s;

% ========== C) Trial-level 合并：分别投票 + 取并集 ==========
n_flag_robust = sum(flag_robust, 2);
n_flag_sigma  = sum(flag_sigma,  2);

reject_robust = n_flag_robust >= vote_M_robust;
reject_sigma  = n_flag_sigma  >= vote_M_sigma;

reject_mask = reject_robust | reject_sigma;
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);

% 打印统计
n_reject_total    = numel(reject_idx);
rate_reject_total = n_reject_total / n_tr;

fprintf('\n==== Trial 检查统计（4-bin locked）====\n');
fprintf('trial 总数: %d\n', n_tr);

fprintf('\n-- 鲁棒策略（RMS log-ratio + postP2P, 条件内MAD-Z） --\n');
fprintf('thr_z = %.2f, vote_M_robust = %d\n', thr_z, vote_M_robust);
fprintf('被鲁棒策略判为剔除: %d (%.2f%%)\n', sum(reject_robust), 100*sum(reject_robust)/n_tr);

fprintf('\n-- 阈值策略（abs阈值 + 全窗P2P 3σ, like/dislike 分开） --\n');
fprintf('abs_threshold = %.1f uV, sigma_p2p = %.2f, vote_M_sigma = %d\n', abs_threshold, sigma_p2p, vote_M_sigma);
fprintf('被阈值策略判为剔除: %d (%.2f%%)\n', sum(reject_sigma), 100*sum(reject_sigma)/n_tr);

fprintf('\n-- 最终并集剔除 --\n');
fprintf('总体剔除: %d (%.2f%%)\n', n_reject_total, 100*rate_reject_total);

% 条件内剔除率
if any(is_nopress)
    n_no = sum(is_nopress); n_rej_no = sum(reject_mask & is_nopress);
    fprintf('  nopress : %d/%d (%.2f%%)\n', n_rej_no, n_no, 100*n_rej_no/max(n_no,1));
end
if any(is_dislike)
    n_dis = sum(is_dislike); n_rej_dis = sum(reject_mask & is_dislike);
    fprintf('  dislike : %d/%d (%.2f%%)\n', n_rej_dis, n_dis, 100*n_rej_dis/max(n_dis,1));
end
if any(is_neutral)
    n_neu = sum(is_neutral); n_rej_neu = sum(reject_mask & is_neutral);
    fprintf('  neutral : %d/%d (%.2f%%)\n', n_rej_neu, n_neu, 100*n_rej_neu/max(n_neu,1));
end
if any(is_like)
    n_like = sum(is_like); n_rej_like = sum(reject_mask & is_like);
    fprintf('  like    : %d/%d (%.2f%%)\n', n_rej_like, n_like, 100*n_rej_like/max(n_like,1));
end

% 每通道命中计数（可分别看两套策略）
rejected_per_channel_robust = sum(flag_robust, 1);
rejected_per_channel_sigma  = sum(flag_sigma,  1);
rejected_per_channel_union  = sum(flag_robust | flag_sigma, 1);

fprintf('\n---- Per-channel hit counts ----\n');
for ch = 1:n_ch
    fprintf('  %-12s robust=%4d | sigma=%4d | union=%4d\n', ...
        ch_names{ch}, ...
        rejected_per_channel_robust(ch), ...
        rejected_per_channel_sigma(ch), ...
        rejected_per_channel_union(ch));
end

% 保存 QC 结果
QC = struct();
QC.subj_id     = subj_id;
QC.epoch_win   = epoch_win;

QC.baseline_win = baseline_win;
QC.post_win     = post_win;

QC.thr_z         = thr_z;
QC.vote_M_robust = vote_M_robust;

QC.abs_threshold = abs_threshold;
QC.sigma_p2p     = sigma_p2p;
QC.vote_M_sigma  = vote_M_sigma;

QC.reject_mask   = reject_mask;
QC.reject_idx    = reject_idx;
QC.keep_idx      = keep_idx;

QC.n_flag_robust = n_flag_robust;
QC.n_flag_sigma  = n_flag_sigma;
QC.reject_robust = reject_robust;
QC.reject_sigma  = reject_sigma;

QC.flag_rms     = flag_rms;
QC.flag_p2p     = flag_p2p;
QC.flag_abs     = flag_abs;
QC.flag_p2p3s   = flag_p2p3s;
QC.flag_robust  = flag_robust;
QC.flag_sigma   = flag_sigma;

QC.rejected_per_channel_robust = rejected_per_channel_robust;
QC.rejected_per_channel_sigma  = rejected_per_channel_sigma;
QC.rejected_per_channel_union  = rejected_per_channel_union;
QC.rate_reject_total           = rate_reject_total;

QC.is_nopress = is_nopress;
QC.is_dislike = is_dislike;
QC.is_neutral = is_neutral;
QC.is_like    = is_like;

save([subj_id '_4binQC_RMSP2P_ROBUST_plus_ABS_P2P3SD.mat'], 'QC');
disp('✔ 已保存 4-bin QC 统计（MAT 文件）');


%% ============================================================
%% (6) 保存 clean epoch
%% ============================================================

EEG_clean = pop_select(EEG,'trial',keep_idx);
EEG_clean.setname = [subj_id '_4bin_epoch_clean'];
pop_saveset(EEG_clean,'filename',[subj_id '_4bin_epoch_clean.set']);

%% ============================================================
%% (7) Time-Frequency (BOSC Morlet)
%% ============================================================

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


fprintf('\n✔ Pipeline finished for %s\n', subj_id);
