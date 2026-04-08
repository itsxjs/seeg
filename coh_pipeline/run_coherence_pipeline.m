%% run_coherence_pipeline.m
% Time-varying linear coherence (EEGLAB epochs) for dyads
% Minimal runnable: 1 subject + 1 dyad (A-H), then expand to multi-subject

clear; clc;

%% ====== 0) 依赖 ======
% 需要 EEGLAB 在 path 中；如果你用 eeglab 工程环境，通常已在 path。
% 否则：addpath('/path/to/eeglab'); eeglab;

%% ====== 1) 路径与被试列表（你需要改这里） ======
data_dir = '/Users/defanive/Desktop/Diploma/seeg分析脚本rate';
out_dir  = '/Users/defanive/Desktop/Diploma/coh_pipeline/coherence_out';
if ~exist(out_dir, 'dir'); mkdir(out_dir); end

sub_list = {'sub001', 'sub005'};   % ✅ 最小可跑：先只放一个
%sub_list = {'sub001','sub004','sub005','sub007','sub008','sub009'}; % 扩展时打开

%% ====== 2) ROI 映射（你提供的；你可以继续加 ROI 或加更多被试） ======
% 这里用结构体 roi_map.(subID).A / .H
roi_map = struct();

roi_map.sub001.A = {'A2-Ref'};
roi_map.sub004.A = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
roi_map.sub005.A = {'A1-Ref','A2-Ref','POL A3','POL L7','POL L8','POL L9','POL L10'};
roi_map.sub007.A = {'A1-Ref','A2-Ref','POL A3','POL A4'};
roi_map.sub008.A = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
roi_map.sub009.A = {'A1-Ref','A2-Ref','POL A3'};

roi_map.sub001.H = {'A1-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref'};
roi_map.sub004.H = {'POL B1','POL B2','POL B3','POL B4','C2-Ref','C3-Ref','C4-Ref'};
roi_map.sub005.H = {'POL B1','POL B2','POL L13','POL L14'};
roi_map.sub007.H = {'POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref'};
roi_map.sub008.H = {'POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'};
roi_map.sub009.H = {'POL B1','POL B2','POL B3'};

%% ====== 3) 条件映射（事件类型 -> 你的三类） ======
cond_map = struct();
cond_map.neg = {'dislike'};   % dislike = neg
cond_map.neu = {'neutral'};   % neutral = neu
cond_map.pos = {'like'};      % like = pos

% "all" = 三类合并（用于 Fig4A 主图）
cond_names = {'all','neg','neu','pos'};

%% ====== 4) coherence 参数（按你需求暴露） ======
params = struct();
params.method    = 'mscohere'; % 或你之后改 cpsd 等
params.freq_range = [2 45];    % Hz（最终截取）
params.win_ms    = 500;        % 滑窗长度
params.step_ms   = 10;         % 步长
params.detrend_each_window = true; % 每窗去线性趋势
params.nfft_mode = 512; % 'nextpow2' 或给定数值
params.verbose   = true;
params.subwin_ms = 250;      % Welch 子窗长度（ms）
params.sub_ovlp  = 0.5;      % overlap 比例（0~0.9）

%% ====== 5) dyad 定义（最小可跑：先只做 A-H） ======
dyads = {
    'A','H'   % Amygdala–Hippocampus
};
% 扩展成多个 dyad 时就继续加：
% dyads = {'A','H'; 'A','OFC'; 'A','mPFC'; 'OFC','mPFC' ...}; % 你后续再补 ROI

%% ====== 6) 循环被试 ======
all_sub_out = cell(numel(sub_list),1);

for si = 1:numel(sub_list)
    sub_id = sub_list{si};
    fprintf('\n===== %s =====\n', sub_id);

    set_path = fullfile(data_dir, sprintf('%s_4bin_epoch_clean.set', sub_id));
    if ~exist(set_path,'file')
        error('找不到文件：%s', set_path);
    end

    EEG = pop_loadset('filename', set_path);

    % 基础检查
    if isempty(EEG.data) || ndims(EEG.data) ~= 3
        error('EEG.data 不是 epoched 3D (chan x time x trial)');
    end
    srate = EEG.srate;
    times_sec = EEG.times(:) / 1000; % EEG.times 通常是 ms

    % 预先构造每个条件的 trial index
    trial_idx = struct();
    % 事件在 epoch 里的匹配：用 epoch.eventtype（最稳），否则回退到 EEG.event
    trial_idx.neg = get_trial_indices_by_eventtype(EEG, cond_map.neg);
    trial_idx.neu = get_trial_indices_by_eventtype(EEG, cond_map.neu);
    trial_idx.pos = get_trial_indices_by_eventtype(EEG, cond_map.pos);
    trial_idx.all = unique([trial_idx.neg(:); trial_idx.neu(:); trial_idx.pos(:)])';

    % 输出结构
    out = struct();
    out.sub_id = sub_id;
    out.params = params;
    out.srate  = srate;
    out.epoch_time_sec = [times_sec(1), times_sec(end)];
    out.n_trials_per_cond = structfun(@(x) numel(x), trial_idx, 'UniformOutput', false);

    coh = struct();

    % ---- dyad 循环（最小可跑只有 A-H） ----
    for di = 1:size(dyads,1)
        roi1 = dyads{di,1};
        roi2 = dyads{di,2};
        dyad_name = sprintf('%s_%s', roi1, roi2);

        if ~isfield(roi_map, sub_id) || ~isfield(roi_map.(sub_id), roi1) || ~isfield(roi_map.(sub_id), roi2)
            warning('%s 缺少 ROI 映射，跳过 dyad %s', sub_id, dyad_name);
            continue;
        end

        % 提取 ROI 信号：[nChan x nTime x nTrial]
        X = extract_roi_signals(EEG, roi_map.(sub_id).(roi1));
        Y = extract_roi_signals(EEG, roi_map.(sub_id).(roi2));

        % 计算：all/neg/neu/pos
        coh_dyad = struct();
        meta_dyad = struct();

        for ci = 1:numel(cond_names)
            cn = cond_names{ci};
            idx = trial_idx.(cn);

            if isempty(idx)
                coh_dyad.(cn) = [];
                meta_dyad.(cn) = struct('n_trials',0,'n_pairs_used',0);
                continue;
            end

            [C_tf, freq_vec, time_vec, meta] = compute_sliding_coherence_pairs( ...
                X(:,:,idx), Y(:,:,idx), srate, times_sec, params);

            coh_dyad.(cn) = C_tf;
            meta_dyad.(cn) = meta;
        end

        coh.(dyad_name) = coh_dyad;
        out.meta.(dyad_name) = meta_dyad;

        % 保存坐标（对所有条件相同，取最后一次成功计算的）
        out.freq_vec_hz  = freq_vec;
        out.time_vec_sec = time_vec;
    end

    out.coh = coh;

    % 保存 mat
    save_path = fullfile(out_dir, sprintf('%s_timevarying_coh.mat', sub_id));
    save(save_path, '-struct', 'out', '-v7.3');
    fprintf('Saved: %s\n', save_path);

    all_sub_out{si} = save_path;

    % ✅ 最小可跑：跑完一个被试就先画一张 dyad all-condition 图检查（显示层平滑+插值）
    dyad_to_plot = 'A_H';
    if isfield(out.coh, dyad_to_plot) && ~isempty(out.coh.(dyad_to_plot).all)
    
        smooth_cfg = struct('do', true, 't_span', 7, 'f_span', 5); % 仅显示平滑
        interp_factor = 4;  % 仅显示插值倍数（越大越细腻，3-6 常用）
    
        fig = plot_coherence_fig4A_style( ...
            out.coh.(dyad_to_plot).all, ...
            out.time_vec_sec, ...
            out.freq_vec_hz, ...
            sprintf('%s %s (all)', sub_id, dyad_to_plot), ...
            [], ...                % clim：先不固定；你后面可以统一 group-level 再回填
            smooth_cfg, ...
            interp_factor);
    
        drawnow;
                % ===== 保存单被试检查图 =====
        fig_name = sprintf('%s_%s_all_coh', sub_id, dyad_to_plot);
        png_path = fullfile(out_dir, [fig_name '.png']);
        % pdf_path = fullfile(out_dir, [fig_name '.pdf']); % 可选

        set(fig, 'PaperPositionMode', 'auto');  % 保持屏幕比例
        exportgraphics(fig, png_path, 'Resolution', 300);
        % exportgraphics(fig, pdf_path, 'ContentType','vector'); % 可选（矢量）

        fprintf('Saved figure: %s\n', png_path);

    end

end

%% ====== 7) group-level 汇总示例（每被试先平均 -> 再 across-subject 平均） ======
% 最小可跑：sub001 一个被试也能跑通；扩展时 sub_list 多个就是真正 group mean
dyad_name = 'A_H';

C_stack = [];
for si = 1:numel(all_sub_out)
    S = load(all_sub_out{si});
    if ~isfield(S, 'coh') || ~isfield(S.coh, dyad_name) || isempty(S.coh.(dyad_name).all)
        continue;
    end
    C_stack = cat(3, C_stack, S.coh.(dyad_name).all); %#ok<AGROW>
    freq_vec = S.freq_vec_hz;
    time_vec = S.time_vec_sec;
end

if ~isempty(C_stack)
    C_group = mean(C_stack, 3, 'omitnan');

    % （可选）先用 group 图自动确定统一色标，再用于其它图
    clim = [min(C_group(:)), max(C_group(:))];

    smooth_cfg = struct('do', true, 't_span', 7, 'f_span', 5);
    interp_factor = 4;

    fig = plot_coherence_fig4A_style( ...
        C_group, ...
        time_vec, ...
        freq_vec, ...
        sprintf('GROUP %s (all)', dyad_name), ...
        clim, ...
        smooth_cfg, ...
        interp_factor);
        % ===== 保存 group 图 =====
    fig_name = sprintf('GROUP_%s_all_coh', dyad_name);
    png_path = fullfile(out_dir, [fig_name '.png']);
    % pdf_path = fullfile(out_dir, [fig_name '.pdf']); % 可选

    set(fig, 'PaperPositionMode', 'auto');
    exportgraphics(fig, png_path, 'Resolution', 300);
    % exportgraphics(fig, pdf_path, 'ContentType','vector'); % 可选

    fprintf('Saved figure: %s\n', png_path);

end

%% ====== 本脚本用到的本地小函数：按事件类型拿 trial index ======
function idx = get_trial_indices_by_eventtype(EEG, event_types)
% 优先用 EEG.epoch(eventtype)，更接近"这个 epoch 属于什么事件"
idx = [];
if isfield(EEG, 'epoch') && isfield(EEG.epoch, 'eventtype')
    for e = 1:numel(EEG.epoch)
        et = EEG.epoch(e).eventtype;
        % et 可能是 cell/char/string
        et_list = string(et);
        if any(ismember(et_list, string(event_types)))
            idx(end+1) = e; %#ok<AGROW>
        end
    end
else
    % 回退：用 EEG.event 的 epoch 字段
    for ev = 1:numel(EEG.event)
        if ~isfield(EEG.event(ev),'epoch'); continue; end
        if any(strcmpi(string(EEG.event(ev).type), string(event_types)))
            idx(end+1) = EEG.event(ev).epoch; %#ok<AGROW>
        end
    end
    idx = unique(idx);
end
idx = unique(idx);
end
