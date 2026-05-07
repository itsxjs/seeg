%% ===== 1) 只添加 '0'->cutoff, '1'->finish 两类情绪事件，且不足2s的跳过 =====
% 假设 EEG 已在工作区；若未载入请先 pop_loadset
subj_id = 'sub001';  % 按需修改
EEG_orig = EEG;

% 参数
epoch_win = [-0.5 2];                  % 计划切段窗口（秒）
srate = EEG.srate;
pre_samp  = round(abs(epoch_win(1)) * srate);
post_samp = round(epoch_win(2)      * srate);

% 工具：把 event.type 统一为 string
toStr = @(x) string(x);  % 兼容 char/string/numeric

% 新事件列表：先拷贝原事件，后面只“追加”通过检查的两类事件
newEvents = EEG.event;
addCount = 0; skipCount = 0;

for i = 1:numel(EEG.event)
    etype = toStr(EEG.event(i).type);

    % 跳过 boundary
    if etype == "boundary"
        continue;
    end

    % 只接受 '0' 和 '1'
    if ~(etype == "0" || etype == "1")
        continue;
    end

    % 映射标签
    lab = '';
    if etype == "0", lab = 'cutoff'; end
    if etype == "1", lab = 'finish'; end

    % 时间边界检查：能否切 [-0.5, 2] s
    lat = EEG.event(i).latency;     % 样本点（可能含小数）
    if (lat - pre_samp < 1) || (lat + post_samp > EEG.pnts)
        skipCount = skipCount + 1;
        continue;  % 不足 2 s（或前 0.5 s），跳过
    end

    % 通过检查则追加一个同 latency 的新事件，type 设置为映射标签
    e2 = EEG.event(i);      % 用原事件做模板，避免字段不一致
    e2.type    = lab;
    e2.latency = EEG.event(i).latency;
    % 不新增新字段，避免结构不一致（如 duration）

    newEvents(end+1) = e2;  %#ok<SAGROW>
    addCount = addCount + 1;
end

EEG.event = newEvents;

% 事件一致性 & 排序
EEG = eeg_checkset(EEG, 'eventconsistency');
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');

fprintf('✔ 已追加事件：%d 条（cutoff/finish），跳过不足窗长度的事件：%d 条。\n', addCount, skipCount);

%% ===== 2) 以 cutoff/finish 切段并保存 =====
EEG = pop_epoch(EEG, {'cutoff','finish'}, epoch_win);
EEG.setname = [subj_id '_bin2_epoch'];  % 两类事件
[ALLEEG, EEG, CURRENTSET] = eeg_store(ALLEEG, EEG, 0);
idxVal = CURRENTSET;
pop_saveset(EEG, 'filename', [subj_id '_bin2_epoch.set']);
fprintf('✔ 已保存 bin2-locked epoch（%.1f~%.1f s）。\n', epoch_win(1), epoch_win(2));

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

% 条件识别（按 epoch 的事件类型）
is_cut = false(n_tr,1);
is_fin = false(n_tr,1);
for k = 1:n_tr
    et = EEG.epoch(k).eventtype;
    if iscell(et), types = string(et); else, types = string({et}); end
    is_cut(k) = any(strcmp(types,'cutoff'));
    is_fin(k) = any(strcmp(types,'finish'));
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

    % cutoff
    if any(is_cut)
        r_ = r(is_cut);  p_ = p2p(is_cut);
        med_r = median(r_); mad_r = max(mad(r_,1), eps_small);
        z_r = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_); mad_p = max(mad(p_,1), eps_small);
        z_p = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_cut);
        flag_rms(idx, ch) = z_r > thr_z;
        flag_p2p(idx, ch) = z_p > thr_z;
    end

    % finish
    if any(is_fin)
        r_ = r(is_fin);  p_ = p2p(is_fin);
        med_r = median(r_); mad_r = max(mad(r_,1), eps_small);
        z_r = 0.6745 * (r_ - med_r) / mad_r;

        med_p = median(p_); mad_p = max(mad(p_,1), eps_small);
        z_p = 0.6745 * (p_ - med_p) / mad_p;

        idx = find(is_fin);
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
n_reject_total = numel(reject_idx);
rate_reject_total = n_reject_total / n_tr;

fprintf('\n==== Trial 检查统计（bin2-locked）====\n');
fprintf('trial 总数: %d\n', n_tr);
fprintf('合并规则: ≥%d 个通道命中 -> 剔除\n', vote_M);
fprintf('总体剔除: %d (%.2f%%)\n', n_reject_total, 100*rate_reject_total);

if any(is_cut)
    n_cut = sum(is_cut); n_rej_cut = sum(reject_mask & is_cut);
    fprintf('  cutoff: %d/%d (%.2f%%)\n', n_rej_cut, n_cut, 100*n_rej_cut/max(n_cut,1));
end
if any(is_fin)
    n_fin = sum(is_fin); n_rej_fin = sum(reject_mask & is_fin);
    fprintf('  finish: %d/%d (%.2f%%)\n', n_rej_fin, n_fin, 100*n_rej_fin/max(n_fin,1));
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
QC.is_cut = is_cut; QC.is_fin = is_fin;

save([subj_id '_bin2QC_RMS_P2P.mat'], 'QC');
disp('✔ 已保存 QC 统计（MAT 文件）');

% 生成 clean 数据集
EEG_bin2_clean = pop_select(ALLEEG(idxVal), 'trial', keep_idx);
EEG_bin2_clean.setname = [subj_id '_bin2_epoch_clean'];
[ALLEEG, EEG_bin2_clean, CURRENTSET] = eeg_store(ALLEEG, EEG_bin2_clean, 0);
pop_saveset(EEG_bin2_clean, 'filename', [subj_id '_bin2_epoch_clean.set']);
disp('✔ 已保存 bin2-locked 删去坏trial的数据');
