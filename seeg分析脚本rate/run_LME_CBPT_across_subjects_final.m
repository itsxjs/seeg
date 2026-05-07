%% LME + CBPT across subjects for TF z-power (2D: Freq × Time)

function run_LME_CBPT_across_subjects_final()
%% ===== 基本参数 =====
subs = {'Sub001','Sub007'};   
data_dir = 'E:\1_Chenglu\IM_sEEG_Chenglu\Data\Processed\Group_analysis';                                          
beh_dir  = 'E:\1_Chenglu\IM_sEEG_Chenglu\Data\Preprocessed\Behavioral_data'; 
lock_types = {'cue','target'};

subj_channels = containers.Map( ...
    {'Sub001', 'Sub007'}, ...   % Fusiform
    { ...
        {'POL E1', 'POL E2', 'POL E3', 'POL E5', 'POL E6', 'POL E7'}, ...  % Sub001 的通道
        {'POL H6', 'POL H7', 'POL H8'}, ...                                % Sub007 的通道
    } ...
);

% 筛选trial
use_qc  = true;
qc_file_template = '%s_cueQC_RMS_P2P.mat';

% 频率处理（二维分析）
freq_band   = [4 7];            % 分析的频段范围（Hz）
ds_ms = 50;                     % 时间下采样（ms）

% 置换次数
nperm = 1000;
rng(42);

% 并行池设置
if isempty(gcp('nocreate'))
    parpool('local');  % 启动并行池，可根据需要指定核心数，如 parpool('local', 8)
end

%% ===== 主流程 =====
for iL = 1:numel(lock_types)
    lock_type = lock_types{iL};
    fprintf('\n===== LME+CBPT 2D (Freq×Time) for %s-locked =====\n', lock_type);

    in_file0 = fullfile(data_dir, sprintf('%s_%s_TF_zpower.mat', subs{1}, lock_type));
    S0 = load_assert(in_file0, {'freqs_eff','tms_win'});
    freqs_eff = S0.freqs_eff(:)';      % Hz
    tms_win   = S0.tms_win(:)';        % ms

    % 频段索引
    [~, f1] = min(abs(freqs_eff - freq_band(1)));
    [~, f2] = min(abs(freqs_eff - freq_band(2)));
    freq_sel = f1:f2;
    freq_vec = freqs_eff(freq_sel);
    nF = numel(freq_sel);

    % 时间下采样索引
    step  = max(1, round(ds_ms / mean(diff(tms_win))));
    t_keep = 1:step:numel(tms_win);
    t_vec  = tms_win(t_keep);
    nT     = numel(t_keep);

    fprintf('  Freq range: %.2f-%.2f Hz (%d points)\n', freq_vec(1), freq_vec(end), nF);
    fprintf('  Time range: %.1f-%.1f ms (%d points)\n', t_vec(1), t_vec(end), nT);

    % ===== 收集跨被试的 (sid:ch:trial) 行 × freq × time 数据 =====
    Y_cell = {}; mode_cell = {}; mem_cell = {}; sid_cell = {}; ch_cell = {};

    for isub = 1:numel(subs)
        sid = subs{isub};
        in_file = fullfile(data_dir, sprintf('%s_%s_TF_zpower.mat', sid, lock_type));
        L = load_assert(in_file, {'z_power','freqs_eff','tms_win','chan_labels'});
        z_power     = L.z_power;          % [trials × chans × freqs × time]
        chan_labels = L.chan_labels;

        if isKey(subj_channels, sid)
            selected_channels = subj_channels(sid);
            ch_idx = ismember(chan_labels, selected_channels);
        else
            ch_idx = true(1, size(z_power, 2));
        end

        % 读取行为
        [mode_vec, mem_vec] = get_behavior_vectors( ...
            sid, lock_type, size(z_power,1), beh_dir, data_dir, use_qc, qc_file_template);

        % 固定 categorical 两水平顺序
        mode_vec = ensure_categorical_2lvl(mode_vec, {'reactive','proactive'});
        mem_vec  = ensure_categorical_2lvl(mem_vec , {'forgotten','remembered'});
        modes = categories(mode_vec);
        mems  = categories(mem_vec);

        % trial 索引（按条件划分）
        idx_cell_cond = cell(2,2);
        for im = 1:2
            for is = 1:2
                idx_cell_cond{im,is} = find(mode_vec==modes{im} & mem_vec==mems{is});
            end
        end

        % ===== 逐通道、逐条件，保留频率维度 =====
        for ch = find(ch_idx)
            for im = 1:2
                for is = 1:2
                    tr_idx = idx_cell_cond{im,is};
                    if isempty(tr_idx), continue; end

                    % 保留频率维度 => [trials × freqs × time]
                    tmp = squeeze(z_power(tr_idx, ch, freq_sel, t_keep));
                    
                    % 处理维度问题
                    if numel(tr_idx) == 1
                        tmp = reshape(tmp, 1, nF, nT);
                    end

                    % 逐 trial 输入
                    for tr = 1:size(tmp,1)
                        Y_cell{end+1,1}    = squeeze(tmp(tr,:,:));  % [freqs × time]
                        mode_cell{end+1,1} = modes{im};       
                        mem_cell{end+1,1}  = mems{is};        
                        sid_cell{end+1,1}  = sid;             
                        ch_cell{end+1,1}   = chan_labels{ch}; 
                    end
                end
            end
        end
    end

    % 合并成 3D 矩阵
    Y = cat(3, Y_cell{:});  % [nF × nT × nRows]
    Y = permute(Y, [3,1,2]); % [nRows × nF × nT]
    nRows = size(Y, 1);
    
    base_tbl = table( categorical(sid_cell), categorical(ch_cell), ...
                      categorical(mode_cell), categorical(mem_cell), ...
                      'VariableNames', {'sid','ch','mode','mem'});

    fprintf('  Total trials collected: %d\n', nRows);

    % ===== 计算各条件的平均 power（用于判断效应方向）=====
    fprintf('  Computing condition-wise averages...\n');
    
    modes = categories(base_tbl.mode);  % {'reactive', 'proactive'}
    mems  = categories(base_tbl.mem);   % {'forgotten', 'remembered'}
    
    % 初始化平均power矩阵
    avg_power = struct();
    avg_power.reactive_forgotten   = nan(nF, nT);
    avg_power.reactive_remembered  = nan(nF, nT);
    avg_power.proactive_forgotten  = nan(nF, nT);
    avg_power.proactive_remembered = nan(nF, nT);
    
    avg_power.reactive   = nan(nF, nT);  % mode 边际平均
    avg_power.proactive  = nan(nF, nT);
    avg_power.forgotten  = nan(nF, nT);  % memory 边际平均
    avg_power.remembered = nan(nF, nT);
    
    % 计算各条件平均
    for f = 1:nF
        for t = 1:nT
            y = Y(:, f, t);
            ok = isfinite(y);
            
            % 四个条件的平均
            idx_rf = ok & base_tbl.mode==modes{1} & base_tbl.mem==mems{1};
            idx_rr = ok & base_tbl.mode==modes{1} & base_tbl.mem==mems{2};
            idx_pf = ok & base_tbl.mode==modes{2} & base_tbl.mem==mems{1};
            idx_pr = ok & base_tbl.mode==modes{2} & base_tbl.mem==mems{2};
            
            if nnz(idx_rf) > 0, avg_power.reactive_forgotten(f,t)   = mean(y(idx_rf)); end
            if nnz(idx_rr) > 0, avg_power.reactive_remembered(f,t)  = mean(y(idx_rr)); end
            if nnz(idx_pf) > 0, avg_power.proactive_forgotten(f,t)  = mean(y(idx_pf)); end
            if nnz(idx_pr) > 0, avg_power.proactive_remembered(f,t) = mean(y(idx_pr)); end
            
            % 边际平均
            idx_r = ok & base_tbl.mode==modes{1};
            idx_p = ok & base_tbl.mode==modes{2};
            idx_f = ok & base_tbl.mem==mems{1};
            idx_m = ok & base_tbl.mem==mems{2};
            
            if nnz(idx_r) > 0, avg_power.reactive(f,t)   = mean(y(idx_r)); end
            if nnz(idx_p) > 0, avg_power.proactive(f,t)  = mean(y(idx_p)); end
            if nnz(idx_f) > 0, avg_power.forgotten(f,t)  = mean(y(idx_f)); end
            if nnz(idx_m) > 0, avg_power.remembered(f,t) = mean(y(idx_m)); end
        end
    end
    
    % 计算效应量（Cohen's d）
    % 先计算各条件的标准差
    std_reactive = nan(nF, nT);
    std_proactive = nan(nF, nT);
    std_forgotten = nan(nF, nT);
    std_remembered = nan(nF, nT);
    
    for f = 1:nF
        for t = 1:nT
            y = Y(:, f, t);
            ok = isfinite(y);
            
            idx_r = ok & base_tbl.mode==modes{1};
            idx_p = ok & base_tbl.mode==modes{2};
            idx_f = ok & base_tbl.mem==mems{1};
            idx_m = ok & base_tbl.mem==mems{2};
            
            if nnz(idx_r) > 1, std_reactive(f,t)   = std(y(idx_r)); end
            if nnz(idx_p) > 1, std_proactive(f,t)  = std(y(idx_p)); end
            if nnz(idx_f) > 1, std_forgotten(f,t)  = std(y(idx_f)); end
            if nnz(idx_m) > 1, std_remembered(f,t) = std(y(idx_m)); end
        end
    end
    
    effect_size = struct();
    % Cohen's d = 均值差 / 合并标准差
    pooled_std_mode = sqrt((std_reactive.^2 + std_proactive.^2) / 2);
    pooled_std_mem = sqrt((std_forgotten.^2 + std_remembered.^2) / 2);
    
    effect_size.mode_d = (avg_power.proactive - avg_power.reactive) ./ pooled_std_mode;
    effect_size.mem_d = (avg_power.remembered - avg_power.forgotten) ./ pooled_std_mem;
    
    % 简单的均值差（更直观）
    effect_size.mode_diff = avg_power.proactive - avg_power.reactive;
    effect_size.mem_diff  = avg_power.remembered - avg_power.forgotten;

    % ===== 逐频率-时间点 LME =====
    fprintf('  Fitting LME per freq-time point (%d × %d = %d fits)...\n', nF, nT, nF*nT);
    
    % 预分配用于 parfor 的变量
    F_mode = nan(nF, nT); P_mode = nan(nF, nT);
    F_mem  = nan(nF, nT); P_mem  = nan(nF, nT);
    F_int  = nan(nF, nT); P_int  = nan(nF, nT);
    
    parfor f = 1:nF
        F_mode_f = nan(1, nT); P_mode_f = nan(1, nT);
        F_mem_f  = nan(1, nT); P_mem_f  = nan(1, nT);
        F_int_f  = nan(1, nT); P_int_f  = nan(1, nT);
        
        for t = 1:nT
            y = Y(:, f, t);
            ok = isfinite(y);
            if nnz(ok) < 32, continue; end

            T = table( ...
                categorical(base_tbl.sid(ok)), ...
                categorical(base_tbl.ch(ok)), ...
                categorical(base_tbl.mode(ok)), ...
                categorical(base_tbl.mem(ok)), ...
                double(y(ok)), ...
                'VariableNames', {'sid','ch','mode','mem','data'});

            try
                mdl = fitlme(T, 'data ~ mode * mem + (1|sid) + (1|sid:ch)', ...
                                'FitMethod','REML','DummyVarCoding','effects');
                A = anova(mdl);
                F_mode_f(t) = A.FStat(2);  P_mode_f(t) = A.pValue(2);
                F_mem_f(t)  = A.FStat(3);  P_mem_f(t)  = A.pValue(3);
                F_int_f(t)  = A.FStat(4);  P_int_f(t)  = A.pValue(4);
            catch ME
                warning('LME failed at f=%d, t=%d: %s', f, t, ME.message);
            end
        end
        
        F_mode(f,:) = F_mode_f; P_mode(f,:) = P_mode_f;
        F_mem(f,:)  = F_mem_f;  P_mem(f,:)  = P_mem_f;
        F_int(f,:)  = F_int_f;  P_int(f,:)  = P_int_f;
    end

    % ===== 置换检验（二维）=====
    fprintf('  Permutations (n=%d) with parfor...\n', nperm);
    uid = strcat(string(base_tbl.sid), "_", string(base_tbl.ch));
    grp = findgroups(uid);
    G = unique(grp)';

    F_mode_null = zeros(nF, nT, nperm);
    F_mem_null  = zeros(nF, nT, nperm);
    F_int_null  = zeros(nF, nT, nperm);

    parfor pp = 1:nperm
        if mod(pp, 100) == 0
            fprintf('    Permutation %d/%d\n', pp, nperm);
        end
        
        mode_perm = base_tbl.mode;
        mem_perm  = base_tbl.mem;

        % 对每个 sid:ch 组，随机打乱标签
        for g = G
            idx = find(grp==g);
            if numel(idx) < 2, continue; end
            ord = randperm(numel(idx));
            mode_perm(idx) = base_tbl.mode(idx(ord));
            mem_perm(idx)  = base_tbl.mem(idx(ord));
        end

        % 逐频率-时间点 LME
        F_mode_pp = nan(nF, nT);
        F_mem_pp  = nan(nF, nT);
        F_int_pp  = nan(nF, nT);
        
        for f = 1:nF
            for t = 1:nT
                y = Y(:, f, t);
                ok = isfinite(y);
                if nnz(ok) < 32, continue; end

                T = table(categorical(base_tbl.sid(ok)), ...
                          categorical(base_tbl.ch(ok)), ...
                          categorical(mode_perm(ok)), ...
                          categorical(mem_perm(ok)), ...
                          double(y(ok)), ...
                          'VariableNames', {'sid','ch','mode','mem','data'});

                try
                    mdlp = fitlme(T, 'data ~ mode * mem + (1|sid) + (1|sid:ch)', ...
                                     'FitMethod','REML','DummyVarCoding','effects');
                    Ap = anova(mdlp);
                    F_mode_pp(f,t) = Ap.FStat(2);
                    F_mem_pp(f,t)  = Ap.FStat(3);
                    F_int_pp(f,t)  = Ap.FStat(4);
                catch
                    % 忽略失败的拟合
                end
            end
        end
        
        F_mode_null(:,:,pp) = F_mode_pp;
        F_mem_null(:,:,pp)  = F_mem_pp;
        F_int_null(:,:,pp)  = F_int_pp;
    end

    % 频率×时间二维簇校正
    fprintf('  Running 2D cluster-based permutation test...\n');
    [h_mode, p_mode_clust, clusterinfo_mode] = cluster_test(F_mode, F_mode_null, 1);
    [h_mem , p_mem_clust , clusterinfo_mem ] = cluster_test(F_mem , F_mem_null , 1);
    [h_int , p_int_clust , clusterinfo_int ] = cluster_test(F_int , F_int_null , 1);

    % 保存结果
    res = struct();
    res.lock_type = lock_type;
    res.freq_vec = freq_vec;
    res.t_vec = t_vec;
    res.freq_band = freq_band;

    res.F_mode = F_mode;  res.P_mode = P_mode;  res.P_mode_clust = p_mode_clust;
    res.h_mode = h_mode;  res.clusterinfo_mode = clusterinfo_mode;
    
    res.F_mem  = F_mem;   res.P_mem  = P_mem;   res.P_mem_clust  = p_mem_clust;
    res.h_mem  = h_mem;   res.clusterinfo_mem  = clusterinfo_mem;
    
    res.F_int  = F_int;   res.P_int  = P_int;   res.P_int_clust  = p_int_clust;
    res.h_int  = h_int;   res.clusterinfo_int  = clusterinfo_int;
    
    % 保存平均power和效应量
    res.avg_power = avg_power;
    res.effect_size = effect_size;

    % 保存文件
    out_name = sprintf('LME_CBPT_2D_%s_FreqTime.mat', lock_type);
    save(fullfile(data_dir, out_name), 'res','subs','freq_band','nperm','-v7.3');
    fprintf('✔ Saved -> %s\n', fullfile(data_dir, out_name));

    % ===== 可视化 =====
    fprintf('  Generating visualizations...\n');
    plot_2D_results(res, data_dir, lock_type);
end

fprintf('\n== 完成：2D Freq×Time LME+CBPT ==\n');

end


%% ===== 可视化函数 =====
function plot_2D_results(res, data_dir, lock_type)
    
    freq_vec = res.freq_vec;
    t_vec = res.t_vec;
    avg_power = res.avg_power;
    effect_size = res.effect_size;
    
    % ===== 图1: F统计量 + 显著簇 =====
    fig1 = figure('Position', [100 100 1400 900]);
    
    % 效应名称
    effects = {'mode', 'mem', 'int'};
    effect_names = {'Mode (Reactive vs Proactive)', ...
                    'Memory (Forgotten vs Remembered)', ...
                    'Mode × Memory Interaction'};
    
    for i = 1:3
        eff = effects{i};
        
        % 提取数据
        F_val = res.(['F_' eff]);
        p_clust = res.(['P_' eff '_clust']);
        h_sig = res.(['h_' eff]);
        
        % 子图1: F统计量
        subplot(3, 3, (i-1)*3 + 1);
        imagesc(t_vec, freq_vec, F_val);
        axis xy;
        colorbar;
        colormap(gca, hot);
        xlabel('Time (ms)');
        ylabel('Frequency (Hz)');
        title(sprintf('%s - F-statistic', effect_names{i}));
        set(gca, 'FontSize', 10);
        
        % 子图2: 簇校正p值（log scale）
        subplot(3, 3, (i-1)*3 + 2);
        p_plot = p_clust;
        p_plot(p_plot == 0) = min(p_plot(p_plot > 0)) / 10;
        imagesc(t_vec, freq_vec, -log10(p_plot));
        axis xy;
        colorbar;
        colormap(gca, parula);
        xlabel('Time (ms)');
        ylabel('Frequency (Hz)');
        title(sprintf('%s - Cluster p-value (-log10)', effect_names{i}));
        hold on;
        caxis([-log10(1) -log10(0.001)]);
        set(gca, 'FontSize', 10);
        
        % 子图3: F值 + 显著簇叠加
        subplot(3, 3, (i-1)*3 + 3);
        imagesc(t_vec, freq_vec, F_val);
        axis xy;
        colorbar;
        colormap(gca, hot);
        xlabel('Time (ms)');
        ylabel('Frequency (Hz)');
        title(sprintf('%s - F-stat + Sig Clusters (p<0.05)', effect_names{i}));
        hold on;
        
        % 叠加显著簇轮廓
        if any(h_sig(:))
            contour(t_vec, freq_vec, double(h_sig), [0.5 0.5], ...
                    'LineColor', 'cyan', 'LineWidth', 2);
            
            % 标记簇中心
            clusterinfo = res.(['clusterinfo_' eff]);
            if isfield(clusterinfo, 'pos_clusters')
                for ic = 1:numel(clusterinfo.pos_clusters)
                    if clusterinfo.pos_clusters(ic).p < 0.05
                        cluster_mask = clusterinfo.pos_clusters(ic).inds;
                        [f_idx, t_idx] = find(cluster_mask);
                        if ~isempty(f_idx)
                            f_center = mean(freq_vec(f_idx));
                            t_center = mean(t_vec(t_idx));
                            plot(t_center, f_center, 'c*', 'MarkerSize', 15, 'LineWidth', 2);
                            text(t_center, f_center, sprintf('p=%.3f', clusterinfo.pos_clusters(ic).p), ...
                                 'Color', 'white', 'FontSize', 9, 'FontWeight', 'bold', ...
                                 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
                        end
                    end
                end
            end
        end
        set(gca, 'FontSize', 10);
    end
    
    sgtitle(sprintf('2D Time-Frequency LME + CBPT Results (%s-locked)', lock_type), ...
            'FontSize', 14, 'FontWeight', 'bold');
    
    % 保存图形1
    fig_name1 = sprintf('LME_CBPT_2D_%s_FreqTime_Fstats.png', lock_type);
    saveas(fig1, fullfile(data_dir, fig_name1));
    fprintf('  ✔ Figure 1 saved -> %s\n', fig_name1);
    
    % ===== 图2: 各条件平均 power + 效应方向 =====
    fig2 = figure('Position', [150 150 1600 1000]);
    
    % Mode 效应
    subplot(3, 3, 1);
    imagesc(t_vec, freq_vec, avg_power.reactive);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Reactive - Mean Power');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 2);
    imagesc(t_vec, freq_vec, avg_power.proactive);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Proactive - Mean Power');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 3);
    imagesc(t_vec, freq_vec, effect_size.mode_diff);
    axis xy; colorbar; colormap(gca, redblue);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Mode Effect: Proactive - Reactive');
    hold on;
    % 叠加显著簇
    if any(res.h_mode(:))
        contour(t_vec, freq_vec, double(res.h_mode), [0.5 0.5], ...
                'LineColor', 'black', 'LineWidth', 2);
    end
    caxis([-max(abs(effect_size.mode_diff(:))) max(abs(effect_size.mode_diff(:)))]);
    set(gca, 'FontSize', 10);
    
    % Memory 效应
    subplot(3, 3, 4);
    imagesc(t_vec, freq_vec, avg_power.forgotten);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Forgotten - Mean Power');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 5);
    imagesc(t_vec, freq_vec, avg_power.remembered);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Remembered - Mean Power');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 6);
    imagesc(t_vec, freq_vec, effect_size.mem_diff);
    axis xy; colorbar; colormap(gca, redblue);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Memory Effect: Remembered - Forgotten');
    hold on;
    if any(res.h_mem(:))
        contour(t_vec, freq_vec, double(res.h_mem), [0.5 0.5], ...
                'LineColor', 'black', 'LineWidth', 2);
    end
    caxis([-max(abs(effect_size.mem_diff(:))) max(abs(effect_size.mem_diff(:)))]);
    set(gca, 'FontSize', 10);
    
    % 四个条件
    subplot(3, 3, 7);
    imagesc(t_vec, freq_vec, avg_power.reactive_forgotten);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Reactive + Forgotten');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 8);
    imagesc(t_vec, freq_vec, avg_power.reactive_remembered);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Reactive + Remembered');
    set(gca, 'FontSize', 10);
    
    subplot(3, 3, 9);
    imagesc(t_vec, freq_vec, avg_power.proactive_forgotten);
    axis xy; colorbar; colormap(gca, jet);
    xlabel('Time (ms)'); ylabel('Frequency (Hz)');
    title('Proactive + Forgotten');
    set(gca, 'FontSize', 10);
    
    % 添加第四个条件到新位置
    figure(fig2);
    ax_extra = axes('Position', [0.72 0.08 0.2 0.22]);
    imagesc(ax_extra, t_vec, freq_vec, avg_power.proactive_remembered);
    axis(ax_extra, 'xy'); 
    colorbar(ax_extra); 
    colormap(ax_extra, jet);
    xlabel(ax_extra, 'Time (ms)'); 
    ylabel(ax_extra, 'Frequency (Hz)');
    title(ax_extra, 'Proactive + Remembered');
    set(ax_extra, 'FontSize', 10);
    
    sgtitle(sprintf('Condition Averages and Effect Directions (%s-locked)', lock_type), ...
            'FontSize', 14, 'FontWeight', 'bold');
    
    % 保存图形2
    fig_name2 = sprintf('LME_CBPT_2D_%s_FreqTime_Averages.png', lock_type);
    saveas(fig2, fullfile(data_dir, fig_name2));
    fprintf('  ✔ Figure 2 saved -> %s\n', fig_name2);
    
    % 打印显著簇信息
    fprintf('\n  === Significant Clusters Summary ===\n');
    for i = 1:3
        eff = effects{i};
        clusterinfo = res.(['clusterinfo_' eff]);
        fprintf('  %s:\n', effect_names{i});
        
        if isfield(clusterinfo, 'pos_clusters')
            n_sig = sum([clusterinfo.pos_clusters.p] < 0.05);
            fprintf('    Found %d significant positive clusters\n', n_sig);
            for ic = 1:numel(clusterinfo.pos_clusters)
                if clusterinfo.pos_clusters(ic).p < 0.05
                    cluster_mask = clusterinfo.pos_clusters(ic).inds;
                    [f_idx, t_idx] = find(cluster_mask);
                    fprintf('      Cluster %d: p=%.4f, stat=%.2f, size=%d pixels\n', ...
                            ic, clusterinfo.pos_clusters(ic).p, ...
                            clusterinfo.pos_clusters(ic).clusterstat, ...
                            nnz(cluster_mask));
                    fprintf('        Freq range: %.2f-%.2f Hz\n', ...
                            min(freq_vec(f_idx)), max(freq_vec(f_idx)));
                    fprintf('        Time range: %.1f-%.1f ms\n', ...
                            min(t_vec(t_idx)), max(t_vec(t_idx)));
                    
                    % ★ 添加效应方向信息
                    if i == 1  % Mode effect
                        mean_diff = mean(effect_size.mode_diff(cluster_mask), 'omitnan');
                        if mean_diff > 0
                            fprintf('        ★ Direction: Proactive > Reactive (diff=%.3f)\n', mean_diff);
                        else
                            fprintf('        ★ Direction: Reactive > Proactive (diff=%.3f)\n', abs(mean_diff));
                        end
                    elseif i == 2  % Memory effect
                        mean_diff = mean(effect_size.mem_diff(cluster_mask), 'omitnan');
                        if mean_diff > 0
                            fprintf('        ★ Direction: Remembered > Forgotten (diff=%.3f)\n', mean_diff);
                        else
                            fprintf('        ★ Direction: Forgotten > Remembered (diff=%.3f)\n', abs(mean_diff));
                        end
                    end
                end
            end
        else
            fprintf('    No significant clusters found\n');
        end
    end
    fprintf('  ===================================\n\n');
end

% redblue colormap for diverging data
function cmap = redblue(m)
    if nargin < 1
        m = 256;
    end
    
    % 创建红-白-蓝配色
    r = [ones(m/2,1); linspace(1,0,m/2)'];
    g = [linspace(0,1,m/2)'; linspace(1,0,m/2)'];
    b = [linspace(0,1,m/2)'; ones(m/2,1)];
    
    cmap = [r g b];
end


%% ===== 辅助函数 =====
function S = load_assert(fname, fields)
    assert(isfile(fname),'文件不存在：%s', fname);
    S = load(fname, '-mat');
    for i=1:numel(fields)
        assert(isfield(S, fields{i}), '文件缺少变量 %s : %s', fields{i}, fname);
    end
end

function out = ternary(cond,a,b), if cond, out=a; else, out=b; end; end

function c = ensure_categorical_2lvl(x, level_names)
    if iscategorical(x)
        c = x;
    elseif islogical(x)
        c = categorical(double(x), [0 1], level_names);
    elseif isnumeric(x)
        assert(all(ismember(unique(x(~isnan(x))), [0 1])), '需要二元 0/1');
        c = categorical(x, [0 1], level_names);
    elseif isstring(x) || iscellstr(x)
        c = categorical(x);
        allcats = categories(c);
        if numel(allcats)==2
            c = renamecats(c, allcats, level_names);
        end
        c = setcats(c, level_names);
    else
        error('未知行为向量类型');
    end
    assert(numel(categories(c))<=2, '行为向量不应超过两类');
    if numel(categories(c))==1
        warning('某数据块某因素只有一个水平；该因素在该部分不可估计。');
    end
end

function [mode_vec, mem_vec] = get_behavior_vectors( ...
    subj_id, lock_type, n_trials_expected, beh_dir, data_dir, use_qc, qc_file_template)

    beh_path = fullfile(beh_dir, [subj_id '_processed_behavior_data.xlsx']);
    assert(isfile(beh_path), '行为表不存在：%s', beh_path);
    T_beh = readtable(beh_path);

    if use_qc
        qc_file = fullfile(data_dir, sprintf(qc_file_template, subj_id));
        if isfile(qc_file)
            SQC = load(qc_file, 'QC');
            keep_idx = SQC.QC.keep_idx(:);
            assert(height(T_beh) >= numel(keep_idx), ...
                '行为表行数(%d) < keep_idx(%d)', height(T_beh), numel(keep_idx));
            T_beh = T_beh(keep_idx, :);
        else
            warning('未找到 QC 文件：%s。将不使用 keep_idx。', qc_file);
        end
    end

    % control 映射
    ctl_raw = lower(string(T_beh.control));
    is_pro  = strcmpi(ctl_raw, 'proactive');
    is_re   = strcmpi(ctl_raw, 'reactive');
    assert(all(is_pro | is_re), 'control 存在非 proactive/reactive 的取值');
    mode_vec = categorical(repmat("reactive", height(T_beh), 1));
    mode_vec(is_pro) = "proactive";
    mode_vec = setcats(mode_vec, {'reactive','proactive'});

    % memory 映射
    mem_raw = lower(string(T_beh.memory));
    is_rem  = strcmpi(mem_raw, 'rem');
    is_forg = strcmpi(mem_raw, 'forg');
    assert(all(is_rem | is_forg), 'memory 存在非 rem/forg 的取值');
    mem_vec  = categorical(repmat("forgotten", height(T_beh), 1));
    mem_vec(is_rem) = "remembered";
    mem_vec = setcats(mem_vec, {'forgotten','remembered'});

    % trial 数对齐检查
    assert(numel(mode_vec)==n_trials_expected && numel(mem_vec)==n_trials_expected, ...
        'trial 对齐失败：%s-%s | mode=%d, mem=%d, EEG=%d', ...
        subj_id, lock_type, numel(mode_vec), numel(mem_vec), n_trials_expected);
end

function [h, p, clusterinfo] = cluster_test(datobs, datrnd, tail, alpha,...
    clusteralpha, clusterstat)
% CLUSTER_TEST performs a cluster-corrected test

if nargin < 3 || isempty(tail)
    tail = 0;
end

if nargin < 4 || isempty(alpha)
    alpha = 0.05;
end

if nargin < 5 || isempty(clusteralpha)
    clusteralpha = 0.05;
end

if nargin < 6 || isempty(clusterstat)
    clusterstat = 'sum';
end

% which dimension contains the randomizations
rndsiz = size(datrnd);
rnddim = numel(rndsiz);
numrnd = rndsiz(rnddim);

if ~( all(size(datobs) == rndsiz(1:end-1)) ||...
        isvector(datobs) && numel(datobs) == rndsiz(1) )
    error('datobs and datrnd are not of compatible dimensionality');
end

cluster_stat_sum = strcmp(clusterstat, 'sum');
cluster_stat_size = strcmp(clusterstat, 'size');
if ~cluster_stat_sum && ~cluster_stat_size
    error('unsupported clusterstat');
end

% determine thresholds for cluster candidates
if tail == 0
    clusteralpha = clusteralpha / 2;
end
cluster_threshold_neg = quantile(datrnd, clusteralpha, rnddim);
cluster_threshold_pos = quantile(datrnd, 1-clusteralpha, rnddim);

% cluster candidates for observed data
[clus_observed_pos, clus_observed_neg, pos_inds, neg_inds] =...
    find_and_characterize_clusters(datobs);

% maximum and minimum cluster statistics for random data
null_pos = nan(numrnd, 1);
null_neg = nan(numrnd, 1);
indvec(1:rnddim) = {':'};
for k = 1:numrnd
    if mod(k, round(numrnd/10)) == 0
        fprintf('      processing permutation %d of %d...\n', k, numrnd);
    end
    
    indvec{rnddim} = k;
    [clus_rnd_pos, clus_rnd_neg] = find_and_characterize_clusters(...
        datrnd(indvec{:}));
    if ~isempty(clus_rnd_pos)
        null_pos(k) = max(clus_rnd_pos);
    end
    if ~isempty(clus_rnd_neg)
        null_neg(k) = min(clus_rnd_neg);
    end
end

null_pos = null_pos(~isnan(null_pos));
null_neg = null_neg(~isnan(null_neg));

null_pos = sort(null_pos, 'descend');
null_neg = sort(null_neg, 'ascend');

% compare observed clusters to null
clus_p_pos = ones(size(clus_observed_pos));
for k = 1:numel(clus_observed_pos)
    clus_p_pos(k) = (sum(null_pos > clus_observed_pos(k)) + 1) / (numrnd+1);
end
clus_p_neg = ones(size(clus_observed_neg));
for k = 1:numel(clus_observed_neg)
    clus_p_neg(k) = (sum(null_neg < clus_observed_neg(k)) + 1) / (numrnd+1);
end

% post-processing of output
if nargout > 2
    clusterinfo = [];
end

% convenient matrix of p-values
p = ones(size(datobs));
if tail >= 0
    for k = 1:numel(clus_p_pos)
        p(pos_inds{k}) = clus_p_pos(k);
        
        if nargout > 2
            clusterinfo.pos_clusters(k).clusterstat = clus_observed_pos(k);
            clusterinfo.pos_clusters(k).p = clus_p_pos(k);
            clusterinfo.pos_clusters(k).inds = false(size(datobs));
            clusterinfo.pos_clusters(k).inds(pos_inds{k}) = 1;
            
            if tail == 0
                clusterinfo.pos_clusters(k).p = clusterinfo.pos_clusters(k).p * 2;
            end
        end
    end
end
if tail <= 0
    for k = 1:numel(clus_p_neg)
        if clus_p_neg(k) < p(neg_inds{k}(1))
            p(neg_inds{k}) = clus_p_neg(k);
        end
        
        if nargout > 2
            clusterinfo.neg_clusters(k).clusterstat = clus_observed_neg(k);
            clusterinfo.neg_clusters(k).p = clus_p_neg(k);
            clusterinfo.neg_clusters(k).inds = false(size(datobs));
            clusterinfo.neg_clusters(k).inds(neg_inds{k}) = 1;
        end
        
        if tail == 0
            clusterinfo.neg_clusters(k).p = clusterinfo.neg_clusters(k).p * 2;
        end
    end
end
if tail == 0
    p = min(1, p .* 2);
end

% result of the hypothesis test
h = p < alpha;

%% nested helper functions
function [clus_stats_pos, clus_stats_neg, pos_inds, neg_inds] = ...
    find_and_characterize_clusters(dat)
    if tail >= 0
        [clus_stats_pos, pos_inds] = compute_cluster_stats(dat,...
            dat >= cluster_threshold_pos);
    end
    if tail <= 0
        [clus_stats_neg, neg_inds] = compute_cluster_stats(dat,...
            dat <= cluster_threshold_neg);
    end

    if tail == -1
        clus_stats_pos = [];
        pos_inds = [];
    elseif tail == 1
        clus_stats_neg = [];
        neg_inds = [];
    end
end

function [clus_stats, inds] = compute_cluster_stats(dat, clus_cand)
    % label the binary masks and compute cluster statistics
    connected = bwconncomp(clus_cand);
    inds = connected.PixelIdxList;
    if cluster_stat_sum
        lens = cellfun(@numel, inds);
        inds = inds(lens > 1);
        clus_stats = zeros(numel(inds),1);
        for l = 1:numel(inds)
            clus_stats(l) = sum(dat(inds{l}));
        end
    elseif cluster_stat_size
        clus_stats = zeros(numel(inds),1);
        for l = 1:connected.NumObjects
            clus_stats(l) = numel(connected.PixelIdxList{l});
        end
    end
end

end