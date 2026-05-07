%% ===== Count trials per condition for each subject =====
clear; clc;

% ===== 被试列表 =====
subs = {'sub001','sub004','sub005','sub007','sub008','sub009'};

% ===== 数据目录 =====
data_dir = pwd;   % 如果不在当前目录，改成你的路径

% ===== 条件标签（与你的 epoch 脚本一致）=====
cond_names = {'negative','neutral','positive'};
n_cond = numel(cond_names);

% ===== 结果容器 =====
subj_col   = strings(numel(subs),1);
count_mat = zeros(numel(subs), n_cond);
total_vec = zeros(numel(subs),1);

fprintf('\n==== Trial counts per subject ====\n');

for i = 1:numel(subs)
    subj_id = subs{i};
    subj_col(i) = subj_id;

    % ---- 优先加载 clean，其次 raw ----
    fn_clean = fullfile(data_dir, sprintf('%s_valence_epoch_clean.set', subj_id));
    fn_raw   = fullfile(data_dir, sprintf('%s_valence_epoch.set', subj_id));

    if exist(fn_clean, 'file')
        EEG = pop_loadset('filename', fn_clean);
        src = 'clean';
    elseif exist(fn_raw, 'file')
        EEG = pop_loadset('filename', fn_raw);
        src = 'raw';
    else
        warning('[%s] 找不到 epoch 文件，跳过', subj_id);
        continue;
    end

    n_tr = EEG.trials;
    total_vec(i) = n_tr;

    % ---- 统计每个 trial 的条件 ----
    is_cond = false(n_tr, n_cond);

    for tr = 1:n_tr
        et = EEG.epoch(tr).eventtype;
        if iscell(et)
            types = string(et);
        else
            types = string({et});
        end

        for c = 1:n_cond
            is_cond(tr, c) = any(types == cond_names{c});
        end
    end

    % ---- 汇总 ----
    count_mat(i,:) = sum(is_cond, 1);

    % ---- 打印 ----
    fprintf('[%s | %s] total=%3d | ', subj_id, src, n_tr);
    for c = 1:n_cond
        fprintf('%s=%3d ', cond_names{c}, count_mat(i,c));
    end
    fprintf('\n');
end

%% ===== 汇总成 table =====
T = table( ...
    subj_col, ...
    total_vec, ...
    count_mat(:,1), ...
    count_mat(:,2), ...
    count_mat(:,3), ...
    'VariableNames', {'subject','total','negative','neutral','positive'});

disp(' ');
disp(T);

% ===== 如需导出 =====
% writetable(T, 'trial_counts_4bin.csv');

%% ===== Count retained channels per subject (ROI-based) =====

% ===== 感兴趣通道列表 =====
subj_channels = struct();
subj_channels.sub001 = {'A1-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref'};
subj_channels.sub004 = {'POL B1','POL B2','POL B3','POL B4','C2-Ref','C3-Ref','C4-Ref'};
subj_channels.sub005 = {'POL B1','POL B2','POL L13','POL L14'};
subj_channels.sub007 = {'POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref'};
subj_channels.sub008 = {'POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'};
subj_channels.sub009 = {'POL B1','POL B2','POL B3'};
% Hippocampus
fprintf('\n==== Channel retention per subject (ROI-based) ====\n');

% 结果容器
chan_total = zeros(numel(subs),1);
chan_keep  = zeros(numel(subs),1);

for i = 1:numel(subs)
    subj_id = subs{i};

    % ---- 检查是否有该被试的通道定义 ----
    if ~isfield(subj_channels, subj_id)
        warning('[%s] 未定义 subj_channels，跳过', subj_id);
        continue;
    end

    roi_chans = subj_channels.(subj_id);
    chan_total(i) = numel(roi_chans);

    % ---- 加载数据（clean 优先）----
    fn_clean = fullfile(data_dir, sprintf('%s_valence_epoch_clean.set', subj_id));
    fn_raw   = fullfile(data_dir, sprintf('%s_valence_epoch.set', subj_id));

    if exist(fn_clean, 'file')
        EEG = pop_loadset('filename', fn_clean);
        src = 'clean';
    elseif exist(fn_raw, 'file')
        EEG = pop_loadset('filename', fn_raw);
        src = 'raw';
    else
        warning('[%s] 找不到 epoch 文件，跳过', subj_id);
        continue;
    end

    have_labels = {EEG.chanlocs.labels};

    % ---- 计算留存通道 ----
    keep = intersect(roi_chans, have_labels, 'stable');
    miss = setdiff(roi_chans, keep);

    chan_keep(i) = numel(keep);

    % ---- 打印 ----
    fprintf('[%s | %s] channels kept: %d / %d\n', ...
        subj_id, src, chan_keep(i), chan_total(i));

    if ~isempty(miss)
        fprintf('   missing: %s\n', strjoin(miss, ', '));
    end
end

%% ===== 汇总成 table =====
T_chan = table( ...
    subj_col, ...
    chan_total, ...
    chan_keep, ...
    chan_keep ./ max(chan_total,1), ...
    'VariableNames', {'subject','roi_total','roi_kept','keep_ratio'});

disp(' ');
disp(T_chan);

% 如需导出
% writetable(T_chan, 'channel_retention_ROI.csv');
