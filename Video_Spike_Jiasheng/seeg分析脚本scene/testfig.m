%使用前确认一下脑区名称！！

%% ===== 画图 =====
plot_valence_results(res, data_dir);

fprintf('\n== DONE: valence (neg vs pos) ==\n');

function squash_y(factor)
% factor: 0~1，越大压得越狠（建议 0.1~0.2）
ax = gca;
pos = ax.Position;
pos(2) = pos(2) + factor/2;
pos(4) = pos(4) - factor;
ax.Position = pos;
end

function style_tf_axes(ax)
set(ax, 'FontSize', 12, 'LineWidth', 1);
xlabel(ax, '时间 (ms)', 'FontSize', 13);
ylabel(ax, '频率 (Hz)', 'FontSize', 13);
end

function plot_valence_results(res, data_dir)

freq_vec = res.freq_vec(:);
t_vec    = res.t_vec(:)';

%% ====== (A) 时间裁剪：去掉最后 500 ms ======
t_end_keep = max(t_vec) - 500;
t_keep = t_vec <= t_end_keep;
t_vec2 = t_vec(t_keep);

% 所有随时间的矩阵做同样裁剪（第2维是 time）
F_val2      = res.F_val(:, t_keep);
P_clust2    = res.P_val_clust(:, t_keep);
h_val2      = res.h_val(:, t_keep);
neg2        = res.avg_val.neg(:, t_keep);
pos2        = res.avg_val.pos(:, t_keep);
diff2       = res.diff_map(:, t_keep);

[TT, FF] = meshgrid(t_vec2, freq_vec);

%% ====== (B) 频率轴：从 2 Hz 起，tick = 2,4,8,16,... ======
fmin = 2;
fmax = max(freq_vec);
ylim_plot = [fmin fmax];

yticks = 2 * 2.^(0:floor(log2(fmax/2)));  % 2,4,8,...
yticks = yticks(yticks >= fmin & yticks <= fmax);

% 一个小 helper，避免每个 subplot 重复写
set_logy = @() set(gca, 'YScale','log', 'YLim',ylim_plot, 'YTick',yticks);

%% ================= 图1: F-stat + cluster p + F-stat(overlay mask) =================
fig1 = figure('Position',[100 100 1200 500]);

% --- (1) LME F-stat ---
subplot(1,3,1);
h1 = surf(TT, FF, F_val2, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, hot);
style_tf_axes(gca);
title('效价效应：线性混合模型F值', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% 记住第一列的色标范围（后面第三列强制一致）
caxF = caxis;

% --- (2) cluster p ---
subplot(1,3,2);
p_plot = P_clust2;
if any(p_plot(:) > 0)
    p_plot(p_plot==0) = min(p_plot(p_plot>0))/10;
else
    p_plot(:) = 1;
end
surf(TT, FF, -log10(p_plot), 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, parula);
style_tf_axes(gca);
title('簇校正p值 (-log10)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% --- (3) F-stat + 叠加显著性 mask（保持与(1)同scale） ---
subplot(1,3,3);
h3 = surf(TT, FF, F_val2, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, hot);
caxis(caxF);   % 关键：强制与第一列相同的 color scale
style_tf_axes(gca);
title('显著簇内F值 (p<0.05)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% 透明度蒙版：显著=1，不显著=0（或很淡）
sig = (h_val2 > 0);
alpha_sig = 1.0;     % 显著区域透明度
alpha_nonsig = 0.0;  % 非显著区域透明度（0=留白；想“变淡”可改成 0.15）

A = alpha_nonsig * ones(size(sig));
A(sig) = alpha_sig;

set(h3, 'FaceAlpha','flat', 'AlphaData', A, 'AlphaDataMapping','none');

sgtitle('情绪效价效应：正性与负性图片比较', 'FontSize', 16, 'FontWeight', 'bold');

saveas(fig1, fullfile(data_dir, 'LME_Hippocampus_CBPT_2D_valence_FreqTime_Fstats.png'));
fprintf('✔ Figure saved: LME_Hippocampus_CBPT_2D_valence_FreqTime_Fstats.png\n');

%% ================= 图2: 条件均值 + 差图（raw & masked） =================
fig2 = figure('Position',[150 150 1600 500]);   % 拉宽一点

%% ---------- (1) negative ----------
subplot(1,4,1);
surf(TT, FF, neg2, 'EdgeColor','none'); 
view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title('负性图片：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

%% ---------- (2) positive ----------
subplot(1,4,2);
surf(TT, FF, pos2, 'EdgeColor','none'); 
view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title('正性图片：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

%% ---------- (3) pos - neg（raw, no mask） ----------
subplot(1,4,3);

hRaw = surf(TT, FF, diff2, 'EdgeColor','none');
view(2);
set_logy(); axis tight; colorbar;
colormap(gca, flipud(redblue));   % 与前两幅语义一致
style_tf_axes(gca);
title('正性 - 负性 (未掩膜)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% 对称色标（后面 masked 图复用）
mx = max(abs(diff2(:)), [], 'omitnan');
if isempty(mx) || mx==0, mx = 1; end
caxis([-mx mx]);

%% ---------- (4) pos - neg（masked by sig clusters） ----------
subplot(1,4,4);

hMask = surf(TT, FF, diff2, 'EdgeColor','none');
view(2);
set_logy(); axis tight; colorbar;
colormap(gca, flipud(redblue));
style_tf_axes(gca);
title('正性 - 负性 (显著簇)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% ★ 强制与 raw 差图完全一致的 scale
caxis([-mx mx]);

% alpha mask：显著=1，非显著=0
sig = (h_val2 > 0);
A = zeros(size(sig));
A(sig) = 1;

set(hMask, 'FaceAlpha','flat', ...
           'AlphaData', A, ...
           'AlphaDataMapping','none');

sgtitle('情绪效价条件均值与差异图', 'FontSize', 16, 'FontWeight', 'bold');

saveas(fig2, fullfile(data_dir, 'LME_Hippocampus_CBPT_2D_valence_FreqTime_Averages.png'));
fprintf('✔ Figure saved: LME_Hippocampus_CBPT_2D_valence_FreqTime_Averages.png\n');

%% =====（可选）打印簇信息时也按 t_keep 裁剪输出范围 =====
if isfield(res,'clusterinfo_val') && isfield(res.clusterinfo_val,'pos_clusters')
    fprintf('\n== Significant clusters (valence) ==\n');
    ci = res.clusterinfo_val;
    for k = 1:numel(ci.pos_clusters)
        if ci.pos_clusters(k).p < 0.05
            mask0 = ci.pos_clusters(k).inds(:, t_keep); % 同步裁剪
            [fi, ti] = find(mask0);
            fprintf('  Cluster %d: p=%.4f, size=%d\n', k, ci.pos_clusters(k).p, nnz(mask0));
            fprintf('    Freq: %.2f - %.2f Hz\n', min(freq_vec(fi)), max(freq_vec(fi)));
            fprintf('    Time: %.1f - %.1f ms\n', min(t_vec2(ti)), max(t_vec2(ti)));
            mean_diff = mean(diff2(mask0),'omitnan');
            if mean_diff > 0
                fprintf('    Direction: POS > NEG (%.3f)\n', mean_diff);
            else
                fprintf('    Direction: NEG > POS (%.3f)\n', abs(mean_diff));
            end
        end
    end
end

end


%% ===== 简单红蓝图 =====
function cmap = redblue(m)
if nargin<1, m=256; end
r = [ones(m/2,1); linspace(1,0,m/2)'];
g = [linspace(0,1,m/2)'; linspace(1,0,m/2)'];
b = [linspace(0,1,m/2)'; ones(m/2,1)];
cmap = [r g b];
end

%% ===== 辅助：load 并检查字段 =====
function S = load_assert(fname, fields)
assert(isfile(fname), '文件不存在: %s', fname);
S = load(fname, '-mat');
for i = 1:numel(fields)
    assert(isfield(S, fields{i}), '文件缺少变量 %s: %s', fields{i}, fname);
end
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
