function plot_study_tf_publication_panels()
%% Publication-style combined TF panels for Study 1 and Study 2.
root_dir = fileparts(fileparts(mfilename('fullpath')));
scene_dir = fullfile(root_dir, 'seeg分析脚本scene');
rate_dir = fullfile(root_dir, 'seeg分析脚本rate');
out_dir = fullfile(root_dir, 'output', 'tf_figures');
if ~exist(out_dir, 'dir')
    mkdir(out_dir);
end

study1 = {
    load(fullfile(scene_dir, 'LME_Amydgala_CBPT_2D_valence_FreqTime.mat')), ...
    load(fullfile(scene_dir, 'LME_Hippocampus_CBPT_2D_valence_FreqTime.mat'))
};
study2 = {
    load(fullfile(rate_dir, 'LME_Amydgala_CBPT_2D_like_dislike_FreqTime.mat')), ...
    load(fullfile(rate_dir, 'LME_Hippocampus_CBPT_2D_like_dislike_FreqTime.mat'))
};

plot_one_study(study1, 'study1', '研究一：正性与负性图片条件下的时频结果', ...
    {'负性图片：平均z功率','正性图片：平均z功率','正性 - 负性（未掩膜）','正性 - 负性（显著簇）'}, ...
    'tf_study1_valence_publication.png', out_dir);

plot_one_study(study2, 'study2', '研究二：喜欢与不喜欢短视频条件下的时频结果', ...
    {'不喜欢条件：平均z功率','喜欢条件：平均z功率','喜欢 - 不喜欢（未掩膜）','喜欢 - 不喜欢（显著簇）'}, ...
    'tf_study2_preference_publication.png', out_dir);
end

function plot_one_study(S, study_code, main_title, avg_titles, out_name, out_dir)
roi_names = {'杏仁核','海马'};
fig = figure('Color','w', 'Position',[100 100 1700 1980], 'Visible','off');
try
    set(fig, 'Toolbar', 'none');
catch
end

layout = make_layout();
letters = {'a','b','c','d'};
letter_i = 1;

for r = 1:2
    res = S{r}.res;
    prepared = prepare_res(res, study_code);

    row_stats = 2*r - 1;
    row_avg = 2*r;

    add_row_letter(fig, letters{letter_i}, row_stats);
    letter_i = letter_i + 1;
    plot_stat_row(fig, prepared, layout, row_stats);

    add_row_letter(fig, letters{letter_i}, row_avg);
    letter_i = letter_i + 1;
    plot_avg_row(fig, prepared, layout, row_avg, avg_titles);
end

out_png = fullfile(out_dir, out_name);
exportgraphics(fig, out_png, 'Resolution', 300);
close(fig);
fprintf('Saved: %s\n', out_png);
end

function P = prepare_res(res, study_code)
P.freq_vec = res.freq_vec(:);
P.t_vec = res.t_vec(:)';
t_end_keep = max(P.t_vec) - 500;
P.t_keep = P.t_vec <= t_end_keep;
P.t_vec2 = P.t_vec(P.t_keep);
[P.TT, P.FF] = meshgrid(P.t_vec2, P.freq_vec);

switch study_code
    case 'study1'
        P.F_val = res.F_val(:, P.t_keep);
        P.p_clust = res.P_val_clust(:, P.t_keep);
        P.sig = res.h_val(:, P.t_keep) > 0;
        P.avg_left = res.avg_val.neg(:, P.t_keep);
        P.avg_right = res.avg_val.pos(:, P.t_keep);
        P.diff = res.diff_map(:, P.t_keep);
    case 'study2'
        P.F_val = res.F_pref(:, P.t_keep);
        P.p_clust = res.P_pref_clust(:, P.t_keep);
        P.sig = res.h_pref(:, P.t_keep) > 0;
        P.avg_left = res.avg_pref.dislike(:, P.t_keep);
        P.avg_right = res.avg_pref.like(:, P.t_keep);
        P.diff = res.diff_map(:, P.t_keep);
    otherwise
        error('Unknown study_code: %s', study_code);
end

P.F_plot = gauss2d(P.F_val, 1.0);
P.p_plot = gauss2d(safe_neglog10(P.p_clust), 1.0);
P.avg_left_plot = gauss2d(P.avg_left, 1.0);
P.avg_right_plot = gauss2d(P.avg_right, 1.0);
P.diff_plot = gauss2d(P.diff, 1.0);

P.yl = [2 max(P.freq_vec)];
P.yticks = 2 * 2.^(0:floor(log2(max(P.freq_vec)/2)));
P.yticks = P.yticks(P.yticks >= 2 & P.yticks <= max(P.freq_vec));
end

function layout = make_layout()
layout.left = 0.105;
layout.width = 0.178;
layout.gap = 0.052;
layout.cb_gap = 0.008;
layout.cb_width = 0.014;
layout.height = 0.165;
layout.row_y = [0.77 0.56 0.31 0.10];
layout.x4 = layout.left + (0:3) * (layout.width + layout.gap);
layout.x3 = layout.left + [0 1 2] * (layout.width + layout.gap);
end

function plot_stat_row(fig, P, layout, row_idx)
y = layout.row_y(row_idx);
titles = {'线性混合模型F值','簇校正p值 (-log10)','显著簇内F值 (p<0.05)'};
data = {P.F_plot, P.p_plot, P.F_plot};
cmaps = {@hot, @parula, @hot};
alphas = {[], [], double(P.sig)};
for i = 1:3
    ax = axes(fig, 'Position', [layout.x3(i) y layout.width layout.height]);
    plot_panel(ax, P, data{i}, cmaps{i}, titles{i}, i == 1, alphas{i});
    add_colorbar(ax, layout);
end
end

function plot_avg_row(fig, P, layout, row_idx, titles)
y = layout.row_y(row_idx);
mx = max(abs(P.diff(:)), [], 'omitnan');
if isempty(mx) || mx == 0, mx = 1; end
data = {P.avg_left_plot, P.avg_right_plot, P.diff_plot, P.diff_plot};
cmaps = {@jet, @jet, @redblue, @redblue};
alphas = {[], [], [], double(P.sig)};
for i = 1:4
    ax = axes(fig, 'Position', [layout.x4(i) y layout.width layout.height]);
    plot_panel(ax, P, data{i}, cmaps{i}, titles{i}, i == 1, alphas{i});
    if i >= 3
        clim(ax, [-mx mx]);
    end
    add_colorbar(ax, layout);
end
end

function plot_panel(ax, P, dat, cmap_fun, ttl, show_y, alpha_data)
surf(ax, P.TT, P.FF, dat, 'EdgeColor','none');
view(ax, 2);
set(ax, 'YScale','log', 'YLim',P.yl, 'YTick',P.yticks, ...
    'YTickLabel', compose('%g', P.yticks), 'FontSize',17, 'LineWidth',1.2);
axis(ax, 'tight');
colormap(ax, cmap_fun(256));
title(ax, ttl, 'FontSize',19, 'FontWeight','bold');
xlabel(ax, '时间 (ms)', 'FontSize',17);
if show_y
    ylabel(ax, '频率 (Hz)', 'FontSize',17);
else
    ylabel(ax, '');
    set(ax, 'YTickLabel', []);
end
grid(ax, 'on');
if ~isempty(alpha_data)
    h = findobj(ax, 'Type','Surface');
    set(h, 'FaceAlpha','flat', 'AlphaData', alpha_data, 'AlphaDataMapping','none');
end
end

function add_colorbar(ax, layout)
pos = ax.Position;
cb = colorbar(ax);
cb.Position = [pos(1)+pos(3)+layout.cb_gap pos(2) layout.cb_width pos(4)];
cb.FontSize = 16;
end

function add_row_letter(fig, letter, row_idx)
layout = make_layout();
y = layout.row_y(row_idx);
annotation(fig, 'textbox', [0.028 y+layout.height-0.01 0.035 0.035], ...
    'String', letter, 'EdgeColor','none', 'FontSize',32, ...
    'FontWeight','bold', 'FontName','Times New Roman');
end

function z = safe_neglog10(p)
p = p;
if any(p(:) > 0)
    p(p == 0) = min(p(p > 0)) / 10;
else
    p(:) = 1;
end
z = -log10(p);
end

function B = gauss2d(A, sigma)
if sigma <= 0
    B = A;
    return;
end
rad = ceil(3*sigma);
x = -rad:rad;
g = exp(-(x.^2)/(2*sigma^2));
g = g / sum(g);
B = conv2(conv2(A, g, 'same'), g', 'same');
end

function cmap = redblue(m)
if nargin < 1
    m = 256;
end
bottom = [0 0 0.5];
botmiddle = [0 0.5 1];
middle = [1 1 1];
topmiddle = [1 0 0];
top = [0.5 0 0];
x = [0 0.25 0.5 0.75 1];
r = [bottom(1) botmiddle(1) middle(1) topmiddle(1) top(1)];
g = [bottom(2) botmiddle(2) middle(2) topmiddle(2) top(2)];
b = [bottom(3) botmiddle(3) middle(3) topmiddle(3) top(3)];
xi = linspace(0,1,m);
cmap = [interp1(x,r,xi)' interp1(x,g,xi)' interp1(x,b,xi)'];
end
