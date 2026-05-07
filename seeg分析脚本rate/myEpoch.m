%% ===== 1) 添加情绪事件：'1'->negative, '2'->neutral, '3'->positive =====
% 假设 EEG 已在工作区；若还未载入，请先 pop_loadset

subj_id = 'sub009';  % 按需修改
EEG_orig = EEG;

% 构造一个新的 event 列表（保留原有事件，再追加新情绪事件）
newEvents = EEG.event;
srate = EEG.srate;

% 小工具：把 event.type 统一转换为字符串来比较
toStr = @(x) string(x);  % 适配 char / string / numeric -> string

addCount = 0;
for i = 1:numel(EEG.event)
    etype = toStr(EEG.event(i).type);
    if etype == "boundary"
        continue; % 跳过边界事件
    end

    % 只处理 '1','2','3' 三类
    if any(etype == ["1","2","3"])
        switch char(etype)
            case '1', lab = 'negative';
            case '2', lab = 'neutral';
            case '3', lab = 'positive';
        end

        % 追加一个新事件：与原始事件同一 latency，type 改为情绪标签
        e2 = EEG.event(i);  % 复制原事件，避免漏字段
        e2.type    = lab;
        e2.latency = EEG.event(i).latency; % 样本点，不改
        % 可选：设置持续时间，表示(-0.5~2s)窗口；epoch 不需要，但留作记录
        %e2.duration = round(2.5 * srate);

        newEvents(end+1) = e2; %#ok<SAGROW>
        addCount = addCount + 1;
    end
end

EEG.event = newEvents;

% 事件一致性 & 排序
EEG = eeg_checkset(EEG, 'eventconsistency');
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');

fprintf('✔ 已追加 %d 个情绪事件（negative/neutral/positive）。\n', addCount);

%% ===== 2) 以情绪事件切段并保存 =====
EEG = pop_epoch(EEG, {'negative','neutral','positive'}, [-0.5 2]);
EEG.setname = [subj_id '_valence_epoch'];
[ALLEEG, EEG, CURRENTSET] = eeg_store(ALLEEG, EEG, 0);
idxVal = CURRENTSET;
pop_saveset(EEG, 'filename', [subj_id '_valence_epoch.set']);
disp('✔ 已保存 valence-locked epoch（-0.5~2s）');

%% ===== 3) 复用你的 QC 逻辑（RMS 比值 + P2P + 鲁棒Z + 投票剔除）=====
EEG = ALLEEG(idxVal);

% 基本参数
tms      = EEG.times;
fs       = EEG.srate;
n_tr     = EEG.trials;
n_ch     = EEG.nbchan;
ch_names = {EEG.chanlocs.labels};

% QC 参数（与你之前一致，可按需调整）
baseline_win = [-500 0];  % ms
post_win     = [0 1000];  % ms
thr_z        = 4;         % 单侧阈值
vote_M       = 5;         % ≥ M 个通道命中则剔除
eps_small    = 1e-12;

% 时间索引检查
base_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
post_idx = find(tms >= post_win(1)     & tms <= post_win(2));
if isempty(base_idx) || isempty(post_idx)
    error('baseline_win 或 post_win 超出 epoch 时间范围，请调整。');
end

% 条件识别：每个 trial 看 epoch 内是否包含目标标签
is_neg = false(n_tr,1);
is_neu = false(n_tr,1);
is_pos = false(n_tr,1);
for k = 1:n_tr
    et = EEG.epoch(k).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_neg(k) = any(strcmp(types,'negative'));
    is_neu(k) = any(strcmp(types,'neutral'));
    is_pos(k) = any(strcmp(types,'positive'));
end

% 预分配
flag_rms = false(n_tr, n_ch);
flag_p2p = false(n_tr, n_ch);

% 指标 + 鲁棒Z（按通道、按条件分别）
for ch = 1:n_ch
    X = squeeze(EEG.data(ch, :, :)).';    % [n_tr x n_time]
    xb = sqrt(mean(X(:, base_idx).^2, 2));
    xp = sqrt(mean(X(:, post_idx).^2,  2));
    r  = log( xp ./ max(xb, eps_small) );
    p2p = max(X(:, post_idx),[],2) - min(X(:, post_idx),[],2);

    % neg
    if any(is_neg)
        r_ = r(is_neg); p_ = p2p(is_neg);
        med_r = median(r_); mad_r = max(mad(r_,1), eps_small);
        z_r = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_); mad_p = max(mad(p_,1), eps_small);
        z_p = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_neg);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % neu
    if any(is_neu)
        r_ = r(is_neu); p_ = p2p(is_neu);
        med_r = median(r_); mad_r = max(mad(r_,1), eps_small);
        z_r = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_); mad_p = max(mad(p_,1), eps_small);
        z_p = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_neu);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % pos
    if any(is_pos)
        r_ = r(is_pos); p_ = p2p(is_pos);
        med_r = median(r_); mad_r = max(mad(r_,1), eps_small);
        z_r = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_); mad_p = max(mad(p_,1), eps_small);
        z_p = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_pos);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end
end

% 合并命中与剔除
flag_ch = flag_rms | flag_p2p;         % trial x chan
n_flag_per_trial = sum(flag_ch, 2);    % 每 trial 命中通道数
reject_mask = n_flag_per_trial >= vote_M;
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);

% 打印统计
rejected_per_channel = sum(flag_ch, 1);
n_reject_total = numel(reject_idx);
rate_reject_total = n_reject_total / n_tr;

fprintf('\n==== Trial 检查统计（valence-locked）====\n');
fprintf('trial 总数: %d\n', n_tr);
fprintf('合并规则: ≥%d 个通道命中 -> 剔除\n', vote_M);
fprintf('总体剔除: %d (%.2f%%)\n', n_reject_total, 100*rate_reject_total);

fprintf('按条件剔除：\n');
if any(is_neg)
    n_neg = sum(is_neg); n_rej_neg = sum(reject_mask & is_neg);
    fprintf('  negative: %d/%d (%.2f%%)\n', n_rej_neg, n_neg, 100*n_rej_neg/max(n_neg,1));
end
if any(is_neu)
    n_neu = sum(is_neu); n_rej_neu = sum(reject_mask & is_neu);
    fprintf('  neutral : %d/%d (%.2f%%)\n', n_rej_neu, n_neu, 100*n_rej_neu/max(n_neu,1));
end
if any(is_pos)
    n_pos = sum(is_pos); n_rej_pos = sum(reject_mask & is_pos);
    fprintf('  positive: %d/%d (%.2f%%)\n', n_rej_pos, n_pos, 100*n_rej_pos/max(n_pos,1));
end

for ch = 1:n_ch
    fprintf('  通道 %-12s 命中计数: %d\n', ch_names{ch}, rejected_per_channel(ch));
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
QC.is_neg = is_neg; QC.is_neu = is_neu; QC.is_pos = is_pos;

save([subj_id '_valenceQC_RMS_P2P.mat'], 'QC');
disp('✔ 已保存 QC 统计（MAT 文件）');

% 生成 clean 数据集（与前面保持一致的思路）
EEG_val_clean = pop_select(ALLEEG(idxVal), 'trial', keep_idx);
EEG_val_clean.setname = [subj_id '_valence_epoch_clean'];
[ALLEEG, EEG_val_clean, CURRENTSET] = eeg_store(ALLEEG, EEG_val_clean, 0);
pop_saveset(EEG_val_clean, 'filename', [subj_id '_valence_epoch_clean.set']);
disp('✔ 已保存 valence-locked 删去坏trial的数据');

