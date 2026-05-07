%% Created on 2025.7.20 by Chenglu 

%%  Output：cue/target epoch + clean + QC统计
% 每个节单独run


% ---------- Preparations ----------
subj_id      = 'Sub005'; %需要修改
data_dir = '/Users/defanive/Desktop/Diploma/LFP预处理-场景'; %需要修改


% ---------- Loading Behaviour Data ----------
behavior_path = fullfile(data_dir, [subj_id '_processed_behavior_data.xlsx']);
behavior = readtable(behavior_path);

% ---------- Create Event Marker ----------
n_events = length(EEG.event);
n_trials = height(behavior);
trial_idx = 1;
for i = 1:2:n_events
    if trial_idx > n_trials, break; end

    % 标记 cue
    control_type = behavior.control{trial_idx};  % 'proactive' / 'reactive'
    if strcmp(control_type, 'proactive')
        EEG.event(i).type = 'pro_cue';
    elseif strcmp(control_type, 'reactive')
        EEG.event(i).type = 're_cue';
    end

    % 标记 target
    memory_status = behavior.memory{trial_idx};  % 'rem' / 'forg'
    if ischar(memory_status) || isstring(memory_status)
        EEG.event(i+1).type = [char(memory_status) '_target']; % rem_target/forg_target
    end

    trial_idx = trial_idx + 1;
end
disp('✔ 已将所有 event 标记为 pro_cue / re_cue / rem_target / forg_target');

% ---------- 生成 cue-locked epoch 并入栈 ----------
EEG_orig = EEG;
EEG = EEG_orig;
EEG = pop_epoch(EEG, {'pro_cue','re_cue'}, [-0.5 2.4]);
EEG.setname = [subj_id '_cue_epoch'];
[ALLEEG, EEG, CURRENTSET] = eeg_store(ALLEEG, EEG, 0);
idxCue = CURRENTSET;
pop_saveset(EEG, 'filename', [subj_id '_cue_epoch.set']);
disp('✔ 已保存 cue-locked epoch');

% ---------- 生成 target-locked epoch 并入栈 ----------
EEG = EEG_orig;
EEG = pop_epoch(EEG, {'rem_target','forg_target'}, [-0.5 2.5]);
EEG.setname = [subj_id '_target_epoch'];
[ALLEEG, EEG, CURRENTSET] = eeg_store(ALLEEG, EEG, 0);
idxTgt = CURRENTSET;
pop_saveset(EEG, 'filename', [subj_id '_target_epoch.set']);
disp('✔ 已保存 target-locked epoch');


%%  在 cue-locked 的epoch上检查每个试次（RMS 比值 + P2P；Pro/Re 分阈值）
EEG = ALLEEG(idxCue);

% 基本参数
tms      = EEG.times;
fs       = EEG.srate;
n_tr     = EEG.trials;
n_ch     = EEG.nbchan;
ch_names = {EEG.chanlocs.labels};


% 检测参数（cue-locked 上）
baseline_win = [-500 0];   % ms
post_win     = [0 1000];    % ms
thr_z        = 4;          % Z单侧阈值
vote_M       = 5;          % trial合并策略：至少 M 个通道命中 -> 剔除（并集=1）
eps_small    = 1e-12;      % 防除零


% 时间窗索引
base_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
post_idx = find(tms >= post_win(1)     & tms <= post_win(2));
if isempty(base_idx) || isempty(post_idx)
    error('baseline_win 或 post_win 超出 epoch 时间范围，请调整。');
end

% 识别 Proactive / Reactive trial
is_pro = false(n_tr,1);
for k = 1:n_tr
    et = EEG.epoch(k).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_pro(k) = any(strcmp(types,'pro_cue'));
end
is_re = ~is_pro;

% 预分配
flag_rms = false(n_tr, n_ch);
flag_p2p = false(n_tr, n_ch);

% 计算指标 + Z（按通道、按条件）
for ch = 1:n_ch
    X = squeeze(EEG.data(ch, :, :)).';           % [n_tr x n_time]
    xb = sqrt(mean(X(:, base_idx).^2, 2));       % baseline RMS
    xp = sqrt(mean(X(:, post_idx).^2,  2));      % post RMS
    r  = log( xp ./ max(xb, eps_small) );        % log(post/base)
    p2p = max(X(:, post_idx),[],2) - min(X(:, post_idx),[],2);

    % Pro 条件
    if any(is_pro)
        r_pro = r(is_pro); p2p_pro = p2p(is_pro);
        med_r = median(r_pro);
        mad_r = mad(r_pro, 1);  mad_r = max(mad_r, eps_small);
        z_r   = 0.6745 * (r_pro - med_r) / mad_r;

        med_p = median(p2p_pro);
        mad_p = mad(p2p_pro, 1); mad_p = max(mad_p, eps_small);
        z_p   = 0.6745 * (p2p_pro - med_p) / mad_p;

        idx = find(is_pro);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % Re 条件
    if any(is_re)
        r_re = r(is_re); p2p_re = p2p(is_re);
        med_r = median(r_re);
        mad_r = mad(r_re, 1);   mad_r = max(mad_r, eps_small);
        z_r   = 0.6745 * (r_re - med_r) / mad_r;

        med_p = median(p2p_re);
        mad_p = mad(p2p_re, 1); mad_p = max(mad_p, eps_small);
        z_p   = 0.6745 * (p2p_re - med_p) / mad_p;

        idx = find(is_re);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end
end

% 通道内并集；trial 层面合并（≥M个通道命中即剔除）
flag_ch = flag_rms | flag_p2p;          % trial x chan
n_flag_per_trial = sum(flag_ch, 2);     % trial 命中通道数
reject_mask = n_flag_per_trial >= vote_M;
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);




%% 务必手动检查之后，然后修改reject_mask，再跑这一部分：生成 clean 数据集

% 统计打印
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);

rejected_per_channel = sum(flag_ch, 1);                 % 每通道剔除计数
n_reject_total = numel(reject_idx);
rate_reject_total = n_reject_total / n_tr;

fprintf('\n==== Trial 检查统计（cue-locked）====\n');
fprintf('trial 总数: %d\n', n_tr);
fprintf('合并规则: ≥%d 个通道命中 -> 剔除\n', vote_M);
fprintf('总体剔除: %d (%.2f%%)\n', n_reject_total, 100*rate_reject_total);

for ch = 1:n_ch
    fprintf('  通道 %-12s 剔除计数: %d\n', ch_names{ch}, rejected_per_channel(ch));
end

n_pro = sum(is_pro); n_recon = sum(is_re);
if n_pro > 0
    n_rej_pro = sum(reject_mask & is_pro);
    fprintf('Pro 条件：%d/%d (%.2f%%)\n', n_rej_pro, n_pro, 100*n_rej_pro/max(n_pro,1));
end
if n_recon > 0
    n_rej_re = sum(reject_mask & is_re);
    fprintf('Re  条件：%d/%d (%.2f%%)\n', n_rej_re, n_recon, 100*n_rej_re/max(n_recon,1));
end

% 保存 QC 结果
QC = struct();
QC.baseline_win = baseline_win;
QC.post_win     = post_win;
QC.thr_z        = thr_z;
QC.vote_M       = vote_M;
QC.reject_mask  = reject_mask;
QC.reject_idx   = reject_idx;
QC.keep_idx     = keep_idx;
QC.rejected_per_channel = rejected_per_channel;
QC.rate_reject_total    = rate_reject_total;
QC.is_pro = is_pro; QC.is_re = is_re;


save([subj_id '_cueQC_RMS_P2P.mat'], 'QC');
disp('✔ 已保存 QC 统计（MAT 文件）');

% cue-clean
EEG_cue_clean = pop_select(ALLEEG(idxCue), 'trial', keep_idx);
EEG_cue_clean.setname = [subj_id '_cue_epoch_clean'];
[ALLEEG, EEG_cue_clean, CURRENTSET] = eeg_store(ALLEEG, EEG_cue_clean, 0);
pop_saveset(EEG_cue_clean, 'filename', [subj_id '_cue_epoch_clean.set']);
disp('已保存cue-locked 删去坏trial的数据');

% target-clean
EEG_tgt = ALLEEG(idxTgt);
EEG_tgt_clean = pop_select(EEG_tgt, 'trial', keep_idx(keep_idx <= EEG_tgt.trials));
EEG_tgt_clean.setname = [subj_id '_target_epoch_clean'];
[ALLEEG, EEG_tgt_clean, CURRENTSET] = eeg_store(ALLEEG, EEG_tgt_clean, 0);
pop_saveset(EEG_tgt_clean, 'filename', [subj_id '_target_epoch_clean.set']);
disp('已保存target-locked 删去坏trial的数据');

disp('已生成 *_epoch.set 与 *_epoch_clean.set，并输出 QC 统计。');


