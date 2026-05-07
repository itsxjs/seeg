%% ===== 1) 只添加 6 类原始事件，合并为 4 类情绪事件并检查窗长 =====
% 假设 EEG 已在工作区；若未载入请先 pop_loadset
subj_id  = 'sub009';  % 按需修改
EEG_orig = EEG;

% 参数
epoch_win = [-0.5 2];                  % 计划切段窗口（秒）
srate     = EEG.srate;
pre_samp  = round(abs(epoch_win(1)) * srate);
post_samp = round(epoch_win(2)       * srate);

% 工具：把 event.type 统一为 string（兼容 char/string/numeric）
toStr = @(x) string(x);

% 新事件列表：先拷贝原事件，后面只“追加”通过检查的四类合并事件
newEvents = EEG.event;
addCount  = 0;
skipCount = 0;

for i = 1:numel(EEG.event)
    etype = toStr(EEG.event(i).type);

    % 跳过 boundary
    if etype == "boundary"
        continue;
    end

    % 只接受 0–5 这 6 种原始事件
    if ~(etype == "0" || etype == "1" || etype == "2" || ...
         etype == "3" || etype == "4" || etype == "5")
        continue;
    end

    % 映射标签：
    % 0 -> 未按键(nopress)
    % 1/2 -> 不喜欢(dislike)
    % 3 -> 中立(neutral)
    % 4/5 -> 喜欢(like)
    lab = '';
    if etype == "0"
        lab = 'nopress';
    elseif etype == "1" || etype == "2"
        lab = 'dislike';
    elseif etype == "3"
        lab = 'neutral';
    elseif etype == "4" || etype == "5"
        lab = 'like';
    end

    % 时间边界检查：能否切 [-0.5, 2] s
    lat = EEG.event(i).latency;   % 样本点（可能含小数）
    if (lat - pre_samp < 1) || (lat + post_samp > EEG.pnts)
        skipCount = skipCount + 1;
        continue;   % 不足窗长度，跳过
    end

    % 通过检查则追加一个同 latency 的新事件，type 设置为合并后的标签
    e2         = EEG.event(i);    % 用原事件做模板，避免字段不一致
    e2.type    = lab;
    e2.latency = EEG.event(i).latency;

    newEvents(end+1) = e2;  %#ok<SAGROW>
    addCount = addCount + 1;
end

EEG.event = newEvents;

% 事件一致性 & 按 latency 排序
EEG = eeg_checkset(EEG, 'eventconsistency');
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');

fprintf('✔ 已追加合并后的情绪事件：%d 条（nopress/dislike/neutral/like），\n', addCount);
fprintf('  跳过不足窗长度的原始事件：%d 条。\n', skipCount);

%% ===== 2) 以 4 类情绪事件切段并保存 =====
EEG = pop_epoch(EEG, {'nopress','dislike','neutral','like'}, epoch_win);
EEG.setname = [subj_id '_4bin_epoch'];   % 四类情绪事件
[ALLEEG, EEG, CURRENTSET] = eeg_store(ALLEEG, EEG, 0);
idxVal = CURRENTSET;
pop_saveset(EEG, 'filename', [subj_id '_4bin_epoch.set']);
fprintf('✔ 已保存 4-bin locked epoch（%.1f~%.1f s）。\n', epoch_win(1), epoch_win(2));

%% ===== 3) QC（RMS 比值 + P2P + 鲁棒Z + 通道投票）=====
EEG = ALLEEG(idxVal);

% 基本参数
tms      = EEG.times;
fs       = EEG.srate;
n_tr     = EEG.trials;
n_ch     = EEG.nbchan;
ch_names = {EEG.chanlocs.labels};

% QC 参数
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

% 预分配
flag_rms = false(n_tr, n_ch);
flag_p2p = false(n_tr, n_ch);

% 指标 + 鲁棒 Z（按通道、按条件分别）
for ch = 1:n_ch
    X  = squeeze(EEG.data(ch, :, :)).';     % [n_tr x n_time]
    xb = sqrt(mean(X(:, base_idx).^2, 2));  % baseline RMS
    xp = sqrt(mean(X(:, post_idx).^2,  2)); % post RMS
    r  = log( xp ./ max(xb, eps_small) );   % log 比值
    p2p = max(X(:, post_idx),[],2) - min(X(:, post_idx),[],2);

    % 一个小 helper：给某个条件做 robust Z，并填 flag
    % （写成局部函数也可以，这里直接展开四次，方便看）
    % 1) nopress
    if any(is_nopress)
        r_   = r(is_nopress);
        p_   = p2p(is_nopress);
        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_nopress);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % 2) dislike
    if any(is_dislike)
        r_   = r(is_dislike);
        p_   = p2p(is_dislike);
        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_dislike);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % 3) neutral
    if any(is_neutral)
        r_   = r(is_neutral);
        p_   = p2p(is_neutral);
        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_neutral);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % 4) like
    if any(is_like)
        r_   = r(is_like);
        p_   = p2p(is_like);
        med_r = median(r_);  mad_r = max(mad(r_,1), eps_small);
        z_r   = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_);  mad_p = max(mad(p_,1), eps_small);
        z_p   = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_like);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end
end

% 合并命中与剔除
flag_ch = flag_rms | flag_p2p;          % trial x chan
n_flag_per_trial = sum(flag_ch, 2);     % 每 trial 命中通道数
reject_mask = n_flag_per_trial >= vote_M;
keep_idx    = find(~reject_mask);
reject_idx  = find(reject_mask);

% 打印统计
rejected_per_channel = sum(flag_ch, 1);
n_reject_total       = numel(reject_idx);
rate_reject_total    = n_reject_total / n_tr;

fprintf('\n==== Trial 检查统计（4-bin locked）====\n');
fprintf('trial 总数: %d\n', n_tr);
fprintf('合并规则: ≥%d 个通道命中 -> 剔除\n', vote_M);
fprintf('总体剔除: %d (%.2f%%)\n', n_reject_total, 100*rate_reject_total);

if any(is_nopress)
    n_no   = sum(is_nopress);
    n_rej_no = sum(reject_mask & is_nopress);
    fprintf('  nopress (未按键): %d/%d (%.2f%%)\n', ...
        n_rej_no, n_no, 100*n_rej_no/max(n_no,1));
end
if any(is_dislike)
    n_dis   = sum(is_dislike);
    n_rej_dis = sum(reject_mask & is_dislike);
    fprintf('  dislike (不喜欢): %d/%d (%.2f%%)\n', ...
        n_rej_dis, n_dis, 100*n_rej_dis/max(n_dis,1));
end
if any(is_neutral)
    n_neu   = sum(is_neutral);
    n_rej_neu = sum(reject_mask & is_neutral);
    fprintf('  neutral (中立): %d/%d (%.2f%%)\n', ...
        n_rej_neu, n_neu, 100*n_rej_neu/max(n_neu,1));
end
if any(is_like)
    n_like   = sum(is_like);
    n_rej_like = sum(reject_mask & is_like);
    fprintf('  like (喜欢): %d/%d (%.2f%%)\n', ...
        n_rej_like, n_like, 100*n_rej_like/max(n_like,1));
end

for ch = 1:n_ch
    fprintf('  通道 %-12s 命中计数: %d\n', ch_names{ch}, rejected_per_channel(ch));
end

% 保存 QC 结果
QC = struct();
QC.epoch_win  = epoch_win;
QC.baseline_win = baseline_win;
QC.post_win     = post_win;
QC.thr_z        = thr_z;
QC.vote_M       = vote_M;
QC.reject_mask  = reject_mask;
QC.reject_idx   = reject_idx;
QC.keep_idx     = keep_idx;
QC.rejected_per_channel = rejected_per_channel;
QC.rate_reject_total    = rate_reject_total;

QC.is_nopress = is_nopress;
QC.is_dislike = is_dislike;
QC.is_neutral = is_neutral;
QC.is_like    = is_like;

save([subj_id '_4binQC_RMS_P2P.mat'], 'QC');
disp('✔ 已保存 4-bin QC 统计（MAT 文件）');

% 生成 clean 数据集
EEG_4bin_clean = pop_select(ALLEEG(idxVal), 'trial', keep_idx);
EEG_4bin_clean.setname = [subj_id '_4bin_epoch_clean'];
[ALLEEG, EEG_4bin_clean, CURRENTSET] = eeg_store(ALLEEG, EEG_4bin_clean, 0);
pop_saveset(EEG_4bin_clean, 'filename', [subj_id '_4bin_epoch_clean.set']);
disp('✔ 已保存 4-bin locked 删去坏 trial 的数据');
