% 使用前确认一下脑区名称！！

%% ===== 画图 =====
data_dir = fileparts(mfilename('fullpath'));  % 输出到当前脚本所在目录
plot_like_dislike_results(res, data_dir);

fprintf('\n== DONE: preference (like vs dislike) ==\n');

%% ===== pow2 y-ticks（2,4,8,16...）=====
function set_pow2_yticks(freq_vec)
yl = [min(freq_vec(:)) max(freq_vec(:))];
p1 = ceil(log2(max(yl(1), eps)));
p2 = floor(log2(yl(2)));
ticks = 2.^(p1:p2);
ticks = ticks(ticks >= 2);

set(gca,'YScale','log');
set(gca,'YLim', yl);
set(gca,'YTick', ticks);
set(gca,'YTickLabel', compose('%g', ticks));
end

function squash_y(factor)
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

%% ===== 主绘图函数（like vs dislike）=====
function plot_like_dislike_results(res, data_dir)

freq_vec = res.freq_vec(:);
t_vec    = res.t_vec(:)';
if isfield(res, 'output_prefix')
    output_prefix = res.output_prefix;
else
    output_prefix = 'LME_Amydgala_CBPT_2D_like_dislike_FreqTime';
end

sigma_vis = 1.0;   % ===== 高斯平滑强度（像素单位，0.5~1.5）=====

%% ===== (A) 时间裁剪：去掉最后 500 ms =====
t_end_keep = max(t_vec) - 500;
t_keep = t_vec <= t_end_keep;
t_vec2 = t_vec(t_keep);

F_pref2   = res.F_pref(:, t_keep);
P_clust2  = res.P_pref_clust(:, t_keep);
h_pref2   = res.h_pref(:, t_keep);

dis2      = res.avg_pref.dislike(:, t_keep);
like2     = res.avg_pref.like(:, t_keep);
diff2     = res.diff_map(:, t_keep);

[TT, FF] = meshgrid(t_vec2, freq_vec);

%% ===== (B) 频率轴设置 =====
fmin = 2;
fmax = max(freq_vec);
ylim_plot = [fmin fmax];
yticks = 2 * 2.^(0:floor(log2(fmax/2)));
yticks = yticks(yticks >= fmin & yticks <= fmax);

set_logy = @() set(gca, 'YScale','log', 'YLim',ylim_plot, 'YTick',yticks);

%% ================= 图1: F / cluster p / masked F =================
fig1 = figure('Position',[100 100 1200 500]);

% --- (1) LME F-stat ---
subplot(1,3,1);
surf(TT, FF, gauss2d(F_pref2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, hot);
style_tf_axes(gca);
title('偏好效应：线性混合模型F值', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)
caxF = caxis;

% --- (2) cluster p ---
subplot(1,3,2);
p_plot = P_clust2;
if any(p_plot(:) > 0)
    p_plot(p_plot==0) = min(p_plot(p_plot>0))/10;
else
    p_plot(:) = 1;
end
surf(TT, FF, gauss2d(-log10(p_plot), sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, parula);
style_tf_axes(gca);
title('簇校正p值 (-log10)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% --- (3) masked F ---
subplot(1,3,3);
hF = surf(TT, FF, gauss2d(F_pref2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, hot);
caxis(caxF);
style_tf_axes(gca);
title('显著簇内F值 (p<0.05)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

sig = (h_pref2 > 0);
A = zeros(size(sig));
A(sig) = 1;
set(hF,'FaceAlpha','flat','AlphaData',A,'AlphaDataMapping','none');

sgtitle('主观偏好效应：喜欢与不喜欢比较', 'FontSize', 16, 'FontWeight', 'bold');

saveas(fig1, fullfile(data_dir, [output_prefix '_Fstats.png']));

%% ================= 图2: 均值 + 差图 =================
fig2 = figure('Position',[150 150 1600 500]);

% --- dislike ---
subplot(1,4,1);
surf(TT, FF, gauss2d(dis2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, jet);
style_tf_axes(gca);
title('不喜欢条件：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% --- like ---
subplot(1,4,2);
surf(TT, FF, gauss2d(like2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, jet);
style_tf_axes(gca);
title('喜欢条件：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

mx = max(abs(diff2(:)), [], 'omitnan');
if isempty(mx) || mx==0, mx = 1; end

% --- raw diff ---
subplot(1,4,3);
surf(TT, FF, gauss2d(diff2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, flipud(redblue));
caxis([-mx mx]);
style_tf_axes(gca);
title('喜欢 - 不喜欢 (未掩膜)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

% --- masked diff ---
subplot(1,4,4);
hD = surf(TT, FF, gauss2d(diff2, sigma_vis), 'EdgeColor','none');
view(2); set_logy(); axis tight;
colorbar; colormap(gca, flipud(redblue));
caxis([-mx mx]);
style_tf_axes(gca);
title('喜欢 - 不喜欢 (显著簇)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25)

A = zeros(size(sig));
A(sig) = 1;
set(hD,'FaceAlpha','flat','AlphaData',A,'AlphaDataMapping','none');

sgtitle('主观偏好条件均值与差异图', 'FontSize', 16, 'FontWeight', 'bold');

saveas(fig2, fullfile(data_dir, [output_prefix '_Averages.png']));

%% ===== 打印显著簇 =====
if isfield(res,'clusterinfo_pref') && isfield(res.clusterinfo_pref,'pos_clusters')
    fprintf('\n== Significant clusters (like vs dislike) ==\n');
    ci = res.clusterinfo_pref;
    for k = 1:numel(ci.pos_clusters)
        if ci.pos_clusters(k).p < 0.05
            mask0 = ci.pos_clusters(k).inds(:, t_keep);
            [fi, ti] = find(mask0);
            fprintf('  Cluster %d: p=%.4f, size=%d\n', ...
                k, ci.pos_clusters(k).p, nnz(mask0));
            fprintf('    Freq: %.2f - %.2f Hz\n', ...
                min(freq_vec(fi)), max(freq_vec(fi)));
            fprintf('    Time: %.1f - %.1f ms\n', ...
                min(t_vec2(ti)), max(t_vec2(ti)));
            vals = diff2(mask0);      % 线性向量
            vals = vals(~isnan(vals));
            if isempty(vals)
                mean_diff = NaN;
            else
                mean_diff = mean(vals);
            end
            if ~isnan(mean_diff) && mean_diff > 0
                fprintf('    Direction: LIKE > DISLIKE (%.3f)\n', mean_diff);
            elseif ~isnan(mean_diff)
                fprintf('    Direction: DISLIKE > LIKE (%.3f)\n', abs(mean_diff));
            else
                fprintf('    Direction: mean diff is NaN (all values NaN in cluster)\n');
            end
        end
    end
end

end

%% ===== 2D Gaussian smoothing（NaN-safe，仅用于可视化）=====
function Zs = gauss2d(Z, sigma)
if nargin<2, sigma=1.0; end
nanmask = isnan(Z);
Z(nanmask)=0;
W = ones(size(Z)); W(nanmask)=0;
Zs = imgaussfilt(Z, sigma, 'FilterSize', 2*ceil(3*sigma)+1);
Ws = imgaussfilt(W, sigma, 'FilterSize', 2*ceil(3*sigma)+1);
Zs = Zs ./ max(Ws, eps);
Zs(nanmask)=NaN;
end

%% ===== red-blue colormap =====
function cmap = redblue(m)
if nargin<1, m=256; end
r = [ones(m/2,1); linspace(1,0,m/2)'];
g = [linspace(0,1,m/2)'; linspace(1,0,m/2)'];
b = [linspace(0,1,m/2)'; ones(m/2,1)];
cmap = [r g b];
end

function out = ternary(cond,a,b)
if cond, out=a; else, out=b; end
end
