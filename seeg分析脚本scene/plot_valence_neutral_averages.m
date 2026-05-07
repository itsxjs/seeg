function plot_valence_neutral_averages()
%% Mean TF maps for study-1 positive/negative vs neutral contrasts.
data_dir = fileparts(mfilename('fullpath'));
subs = {'sub001', 'sub004', 'sub005', 'sub007', 'sub008', 'sub009'};
rois = make_roi_configs();
contrasts = {
    struct('code','pos_neu', 'a','pos', 'b','neu', ...
           'a_title','正性图片', 'b_title','中性图片', ...
           'diff_title','正性 - 中性', 'sg_prefix','正性与中性图片比较');
    struct('code','neg_neu', 'a','neg', 'b','neu', ...
           'a_title','负性图片', 'b_title','中性图片', ...
           'diff_title','负性 - 中性', 'sg_prefix','负性与中性图片比较')
};

for r = 1:numel(rois)
    for c = 1:numel(contrasts)
        fprintf('\nPlotting %s %s...\n', rois(r).name, contrasts{c}.code);
        res = collect_pair_means(data_dir, subs, rois(r), contrasts{c});
        out_prefix = sprintf('Mean_%s_2D_%s_FreqTime', rois(r).prefix, contrasts{c}.code);
        save(fullfile(data_dir, [out_prefix '.mat']), 'res', '-v7.3');
        plot_pair(res, data_dir, out_prefix);
    end
end
end

function rois = make_roi_configs()
hip = struct();
hip.name = '海马';
hip.prefix = 'Hippocampus';
hip.channels.sub001 = {'A1-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref'};
hip.channels.sub004 = {'POL B1','POL B2','POL B3','POL B4','C2-Ref','C3-Ref','C4-Ref'};
hip.channels.sub005 = {'POL B1','POL B2','POL L13','POL L14'};
hip.channels.sub007 = {'POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref'};
hip.channels.sub008 = {'POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'};
hip.channels.sub009 = {'POL B1','POL B2','POL B3'};

amy = struct();
amy.name = '杏仁核';
amy.prefix = 'Amydgala';
amy.channels.sub001 = {'A2-Ref'};
amy.channels.sub004 = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
amy.channels.sub005 = {'A1-Ref','A2-Ref','POL A3','POL L7','POL L8','POL L9','POL L10'};
amy.channels.sub007 = {'A1-Ref','A2-Ref','POL A3','POL A4'};
amy.channels.sub008 = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
amy.channels.sub009 = {'A1-Ref','A2-Ref','POL A3'};
rois = [amy, hip];
end

function res = collect_pair_means(data_dir, subs, roi, contrast)
all_a = {};
all_b = {};
for isub = 1:numel(subs)
    sid = subs{isub};
    S = load(fullfile(data_dir, sprintf('%s_valence_scene_TF_zpower.mat', sid)));
    chans = S.chan_labels;
    if isfield(roi.channels, sid)
        keep_ch = ismember(chans, roi.channels.(sid));
    else
        keep_ch = true(1, numel(chans));
    end
    masks.neg = S.is_neg(:);
    masks.neu = S.is_neu(:);
    masks.pos = S.is_pos(:);

    zpow = S.z_power_ds;
    for ch = find(keep_ch)
        idx_a = find(masks.(contrast.a));
        idx_b = find(masks.(contrast.b));
        if ~isempty(idx_a)
            all_a{end+1,1} = squeeze(mean(zpow(idx_a, ch, :, :), 1, 'omitnan'));
        end
        if ~isempty(idx_b)
            all_b{end+1,1} = squeeze(mean(zpow(idx_b, ch, :, :), 1, 'omitnan'));
        end
    end
end

a_stack = cat(3, all_a{:});
b_stack = cat(3, all_b{:});
avg_a = mean(a_stack, 3, 'omitnan');
avg_b = mean(b_stack, 3, 'omitnan');

res = struct();
res.roi = roi.name;
res.roi_prefix = roi.prefix;
res.contrast = contrast;
res.freq_vec = S.freqs(:)';
res.t_vec = S.tms_ds(:)';
res.avg_a = avg_a;
res.avg_b = avg_b;
res.diff_map = avg_a - avg_b;
res.n_a_maps = size(a_stack, 3);
res.n_b_maps = size(b_stack, 3);
end

function plot_pair(res, data_dir, out_prefix)
freq_vec = res.freq_vec(:);
t_vec = res.t_vec(:)';
t_end_keep = max(t_vec) - 500;
t_keep = t_vec <= t_end_keep;
t_vec2 = t_vec(t_keep);
[TT, FF] = meshgrid(t_vec2, freq_vec);

sigma_vis = 1.0;
a_plot = gauss2d(res.avg_a(:, t_keep), sigma_vis);
b_plot = gauss2d(res.avg_b(:, t_keep), sigma_vis);
diff_plot = gauss2d(res.diff_map(:, t_keep), sigma_vis);

fmin = 2;
fmax = max(freq_vec);
ylim_plot = [fmin fmax];
yticks = 2 * 2.^(0:floor(log2(fmax/2)));
yticks = yticks(yticks >= fmin & yticks <= fmax);
set_logy = @() set(gca, 'YScale','log', 'YLim',ylim_plot, 'YTick',yticks);

fig = figure('Position',[100 100 1200 500]);
subplot(1,3,1);
surf(TT, FF, a_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title([res.contrast.a_title '：平均z功率'], 'FontSize', 14, 'FontWeight', 'bold');

subplot(1,3,2);
surf(TT, FF, b_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title([res.contrast.b_title '：平均z功率'], 'FontSize', 14, 'FontWeight', 'bold');

subplot(1,3,3);
mx = max(abs(res.diff_map(:, t_keep)), [], 'all', 'omitnan');
if isempty(mx) || mx == 0, mx = 1; end
surf(TT, FF, diff_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, flipud(redblue)); caxis([-mx mx]);
style_tf_axes(gca);
title([res.contrast.diff_title '：差异图'], 'FontSize', 14, 'FontWeight', 'bold');

sgtitle(sprintf('%s：%s条件均值与差异图', res.roi, res.contrast.sg_prefix), ...
    'FontSize', 16, 'FontWeight', 'bold');
saveas(fig, fullfile(data_dir, [out_prefix '_Averages.png']));
close(fig);
end

function style_tf_axes(ax)
set(ax, 'FontSize', 12, 'LineWidth', 1);
xlabel(ax, '时间 (ms)', 'FontSize', 13);
ylabel(ax, '频率 (Hz)', 'FontSize', 13);
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
    m = size(get(gcf,'colormap'),1);
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
