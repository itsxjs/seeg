function run_LME_CBPT_valence_neutral_pairwise_nperm100()
%% Pairwise LME + CBPT for study-1 valence-neutral contrasts.
data_dir = fileparts(mfilename('fullpath'));
subs = {'sub001', 'sub004', 'sub005', 'sub007', 'sub008', 'sub009'};
nperm = 100;
rng(42);

rois = make_roi_configs();
contrasts = {
    struct('code','pos_neu', 'a','pos', 'b','neu', ...
           'a_title','正性图片', 'b_title','中性图片', ...
           'diff_title','正性 - 中性', ...
           'sg_prefix','正性与中性图片比较');
    struct('code','neg_neu', 'a','neg', 'b','neu', ...
           'a_title','负性图片', 'b_title','中性图片', ...
           'diff_title','负性 - 中性', ...
           'sg_prefix','负性与中性图片比较')
};

if isempty(gcp('nocreate'))
    parpool('local');
end

for r = 1:numel(rois)
    for c = 1:numel(contrasts)
        fprintf('\n===== %s: %s =====\n', rois(r).name, contrasts{c}.code);
        res = run_one_pair(data_dir, subs, rois(r), contrasts{c}, nperm);
        out_prefix = sprintf('LME_%s_CBPT_2D_%s_FreqTime_nperm100', rois(r).prefix, contrasts{c}.code);
        out_mat = fullfile(data_dir, [out_prefix '.mat']);
        save(out_mat, 'res', '-v7.3');
        fprintf('Saved: %s\n', out_mat);
        plot_pair_results(res, data_dir, out_prefix);
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

function res = run_one_pair(data_dir, subs, roi, contrast, nperm)
first_file = fullfile(data_dir, sprintf('%s_valence_scene_TF_zpower.mat', subs{1}));
S0 = load_assert(first_file, {'z_power_ds','freqs','tms_ds','chan_labels','is_neg','is_neu','is_pos'});
freq_vec = S0.freqs(:)';
t_vec = S0.tms_ds(:)';
nF = numel(freq_vec);
nT = numel(t_vec);
freq_sel = 1:nF;
t_keep = 1:nT;

Y_cell = {};
sid_cell = {};
ch_cell = {};
cond_cell = {};

for isub = 1:numel(subs)
    sid = subs{isub};
    infile = fullfile(data_dir, sprintf('%s_valence_scene_TF_zpower.mat', sid));
    S = load_assert(infile, {'z_power_ds','freqs','tms_ds','chan_labels','is_neg','is_neu','is_pos'});
    zpow = S.z_power_ds;
    chans = S.chan_labels;
    masks.neg = S.is_neg(:);
    masks.neu = S.is_neu(:);
    masks.pos = S.is_pos(:);

    if isfield(roi.channels, sid)
        keep_ch = ismember(chans, roi.channels.(sid));
    else
        keep_ch = true(1, numel(chans));
    end

    use_trials = find(masks.(contrast.a) | masks.(contrast.b));
    for ch = find(keep_ch)
        for tr = use_trials'
            patch = squeeze(zpow(tr, ch, freq_sel, t_keep));
            if numel(patch) ~= nF*nT
                continue;
            end
            Y_cell{end+1,1} = patch;
            sid_cell{end+1,1} = sid;
            ch_cell{end+1,1} = chans{ch};
            if masks.(contrast.a)(tr)
                cond_cell{end+1,1} = contrast.a;
            else
                cond_cell{end+1,1} = contrast.b;
            end
        end
    end
end

Y = cat(3, Y_cell{:});
Y = permute(Y, [3 1 2]);
nRows = size(Y, 1);
base_tbl = table(categorical(sid_cell), categorical(ch_cell), categorical(cond_cell), ...
    'VariableNames', {'sid','ch','valence'});
fprintf('Collected %d observations (trial x channel)\n', nRows);

avg_val = struct();
avg_val.(contrast.a) = nan(nF,nT);
avg_val.(contrast.b) = nan(nF,nT);
for f = 1:nF
    for t = 1:nT
        y = Y(:,f,t);
        ok = isfinite(y);
        idx_a = ok & strcmp(string(base_tbl.valence), contrast.a);
        idx_b = ok & strcmp(string(base_tbl.valence), contrast.b);
        if any(idx_a), avg_val.(contrast.a)(f,t) = mean(y(idx_a)); end
        if any(idx_b), avg_val.(contrast.b)(f,t) = mean(y(idx_b)); end
    end
end
diff_map = avg_val.(contrast.a) - avg_val.(contrast.b);

F_val = nan(nF,nT);
P_val = nan(nF,nT);
fprintf('Fitting LME per freq-time (%d x %d)...\n', nF, nT);
for f = 1:nF
    F_f = nan(1,nT);
    P_f = nan(1,nT);
    for t = 1:nT
        y = Y(:,f,t);
        ok = isfinite(y);
        if nnz(ok) < 20, continue; end
        T = table(categorical(base_tbl.sid(ok)), categorical(base_tbl.ch(ok)), ...
            categorical(base_tbl.valence(ok)), double(y(ok)), ...
            'VariableNames', {'sid','ch','valence','data'});
        try
            mdl = fitlme(T, 'data ~ valence + (1|sid) + (1|sid:ch)', ...
                'FitMethod','REML','DummyVarCoding','effects');
            A = anova(mdl);
            F_f(t) = A.FStat(2);
            P_f(t) = A.pValue(2);
        catch ME
            warning('LME fail f=%d,t=%d: %s', f, t, ME.message);
        end
    end
    F_val(f,:) = F_f;
    P_val(f,:) = P_f;
end

fprintf('Permutations n=%d ...\n', nperm);
uid = strcat(string(base_tbl.sid), "_", string(base_tbl.ch));
grp = findgroups(uid);
G = unique(grp)';
F_null = zeros(nF, nT, nperm);
parfor pp = 1:nperm
    val_perm = base_tbl.valence;
    for g = G
        idx = find(grp==g);
        if numel(idx) > 1
            ord = randperm(numel(idx));
            val_perm(idx) = val_perm(idx(ord));
        end
    end

    F_pp = nan(nF,nT);
    for f = 1:nF
        for t = 1:nT
            y = Y(:,f,t);
            ok = isfinite(y);
            if nnz(ok) < 20, continue; end
            T = table(categorical(base_tbl.sid(ok)), categorical(base_tbl.ch(ok)), ...
                categorical(val_perm(ok)), double(y(ok)), ...
                'VariableNames', {'sid','ch','valence','data'});
            try
                mdlp = fitlme(T, 'data ~ valence + (1|sid) + (1|sid:ch)', ...
                    'FitMethod','REML','DummyVarCoding','effects');
                Ap = anova(mdlp);
                F_pp(f,t) = Ap.FStat(2);
            catch
            end
        end
    end
    F_null(:,:,pp) = F_pp;
end

fprintf('Cluster-based correction...\n');
[h_val, p_val_clust, clusterinfo_val] = cluster_test(F_val, F_null, 1);

res = struct();
res.roi = roi.name;
res.roi_prefix = roi.prefix;
res.contrast = contrast;
res.subs = subs;
res.freq_vec = freq_vec;
res.t_vec = t_vec;
res.F_val = F_val;
res.P_val = P_val;
res.P_val_clust = p_val_clust;
res.h_val = h_val;
res.clusterinfo_val = clusterinfo_val;
res.avg_val = avg_val;
res.diff_map = diff_map;
res.nperm = nperm;
end

function plot_pair_results(res, data_dir, out_prefix)
freq_vec = res.freq_vec(:);
t_vec = res.t_vec(:)';
t_end_keep = max(t_vec) - 500;
t_keep = t_vec <= t_end_keep;
t_vec2 = t_vec(t_keep);

F_val2 = res.F_val(:, t_keep);
P_clust2 = res.P_val_clust(:, t_keep);
h_val2 = res.h_val(:, t_keep);
a2 = res.avg_val.(res.contrast.a)(:, t_keep);
b2 = res.avg_val.(res.contrast.b)(:, t_keep);
diff2 = res.diff_map(:, t_keep);
[TT, FF] = meshgrid(t_vec2, freq_vec);

sigma_vis = 1.0;
F_plot = gauss2d(F_val2, sigma_vis);
a_plot = gauss2d(a2, sigma_vis);
b_plot = gauss2d(b2, sigma_vis);
diff_plot = gauss2d(diff2, sigma_vis);

fmin = 2;
fmax = max(freq_vec);
ylim_plot = [fmin fmax];
yticks = 2 * 2.^(0:floor(log2(fmax/2)));
yticks = yticks(yticks >= fmin & yticks <= fmax);
set_logy = @() set(gca, 'YScale','log', 'YLim',ylim_plot, 'YTick',yticks);

fig1 = figure('Position',[100 100 1200 500]);
subplot(1,3,1);
surf(TT, FF, F_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, hot);
style_tf_axes(gca);
title('线性混合模型F值', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);
caxF = caxis;

subplot(1,3,2);
p_plot = P_clust2;
if any(p_plot(:) > 0)
    p_plot(p_plot==0) = min(p_plot(p_plot>0))/10;
else
    p_plot(:) = 1;
end
surf(TT, FF, gauss2d(-log10(p_plot), sigma_vis), 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, parula);
style_tf_axes(gca);
title('簇校正p值 (-log10)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);

subplot(1,3,3);
hF = surf(TT, FF, F_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, hot); caxis(caxF);
style_tf_axes(gca);
title('显著簇内F值 (p<0.05)', 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);
sig = h_val2 > 0;
A = zeros(size(sig)); A(sig) = 1;
set(hF, 'FaceAlpha','flat', 'AlphaData', A, 'AlphaDataMapping','none');
sgtitle(sprintf('%s：%s', res.roi, res.contrast.sg_prefix), ...
    'FontSize', 16, 'FontWeight', 'bold');
saveas(fig1, fullfile(data_dir, [out_prefix '_Fstats.png']));
close(fig1);

fig2 = figure('Position',[150 150 1600 500]);
subplot(1,4,1);
surf(TT, FF, a_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title([res.contrast.a_title '：平均z功率'], 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);

subplot(1,4,2);
surf(TT, FF, b_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, jet);
style_tf_axes(gca);
title([res.contrast.b_title '：平均z功率'], 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);

mx = max(abs(diff2(:)), [], 'omitnan');
if isempty(mx) || mx == 0, mx = 1; end
subplot(1,4,3);
surf(TT, FF, diff_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, flipud(redblue)); caxis([-mx mx]);
style_tf_axes(gca);
title([res.contrast.diff_title ' (未掩膜)'], 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);

subplot(1,4,4);
hD = surf(TT, FF, diff_plot, 'EdgeColor','none'); view(2);
set_logy(); axis tight; colorbar; colormap(gca, flipud(redblue)); caxis([-mx mx]);
style_tf_axes(gca);
title([res.contrast.diff_title ' (显著簇)'], 'FontSize', 14, 'FontWeight', 'bold');
squash_y(0.25);
A = zeros(size(sig)); A(sig) = 1;
set(hD, 'FaceAlpha','flat', 'AlphaData', A, 'AlphaDataMapping','none');
sgtitle(sprintf('%s：%s条件均值与差异图', res.roi, res.contrast.sg_prefix), ...
    'FontSize', 16, 'FontWeight', 'bold');
saveas(fig2, fullfile(data_dir, [out_prefix '_Averages.png']));
close(fig2);

print_clusters(res, t_keep, t_vec2);
end

function print_clusters(res, t_keep, t_vec2)
fprintf('\n== Significant clusters (%s %s) ==\n', res.roi, res.contrast.code);
ci = res.clusterinfo_val;
if ~isfield(ci, 'pos_clusters')
    return;
end
freq_vec = res.freq_vec;
for k = 1:numel(ci.pos_clusters)
    if ci.pos_clusters(k).p < 0.05
        mask0 = ci.pos_clusters(k).inds(:, t_keep);
        [fi, ti] = find(mask0);
        if isempty(fi)
            continue;
        end
        fprintf('  Cluster %d: p=%.4f, size=%d\n', k, ci.pos_clusters(k).p, nnz(mask0));
        fprintf('    Freq: %.2f - %.2f Hz\n', min(freq_vec(fi)), max(freq_vec(fi)));
        fprintf('    Time: %.1f - %.1f ms\n', min(t_vec2(ti)), max(t_vec2(ti)));
        diff0 = res.diff_map(:, t_keep);
        mean_diff = mean(diff0(mask0), 'omitnan');
        if mean_diff >= 0
            fprintf('    Direction: %s > %s (%.3f)\n', res.contrast.a, res.contrast.b, mean_diff);
        else
            fprintf('    Direction: %s > %s (%.3f)\n', res.contrast.b, res.contrast.a, abs(mean_diff));
        end
    end
end
end

function style_tf_axes(ax)
set(ax, 'FontSize', 12, 'LineWidth', 1);
xlabel(ax, '时间 (ms)', 'FontSize', 13);
ylabel(ax, '频率 (Hz)', 'FontSize', 13);
end

function squash_y(factor)
ax = gca;
pos = ax.Position;
pos(2) = pos(2) + factor/2;
pos(4) = pos(4) - factor;
ax.Position = pos;
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

function S = load_assert(fn, req)
if ~exist(fn, 'file')
    error('Missing file: %s', fn);
end
S = load(fn);
for i = 1:numel(req)
    if ~isfield(S, req{i})
        error('File %s missing variable: %s', fn, req{i});
    end
end
end

function [h, p, clusterinfo] = cluster_test(datobs, datrnd, tail, alpha, clusteralpha, clusterstat)
if nargin < 4 || isempty(alpha), alpha = 0.05; end
if nargin < 5 || isempty(clusteralpha), clusteralpha = 0.05; end
if nargin < 6 || isempty(clusterstat), clusterstat = 'sum'; end

dimord = size(datobs);
rndsize = size(datrnd);
if numel(rndsize) < numel(dimord) || any(rndsize(1:numel(dimord)) ~= dimord)
    error('datrnd first dimensions must match datobs. datobs=%s, datrnd=%s', ...
        mat2str(dimord), mat2str(rndsize));
end
rnddim = numel(dimord) + 1;
if numel(rndsize) < rnddim
    error('datrnd must include a permutation dimension after datobs dimensions.');
end
numrnd = size(datrnd, rnddim);

indvec = cell(1, ndims(datrnd));
cluster_stat_sum = strcmp(clusterstat, 'sum');
cluster_stat_size = strcmp(clusterstat, 'size');
if ~cluster_stat_sum && ~cluster_stat_size
    error('unsupported clusterstat');
end

if tail == 0
    clusteralpha = clusteralpha / 2;
end
cluster_threshold_neg = quantile(datrnd, clusteralpha, rnddim);
cluster_threshold_pos = quantile(datrnd, 1-clusteralpha, rnddim);

[clus_observed_pos, clus_observed_neg, pos_inds, neg_inds] = find_and_characterize_clusters(datobs);

null_pos = nan(numrnd, 1);
null_neg = nan(numrnd, 1);
indvec(1:rnddim) = {':'};
for k = 1:numrnd
    if mod(k, round(numrnd/10)) == 0
        fprintf('      processing permutation %d of %d...\n', k, numrnd);
    end
    indvec{rnddim} = k;
    [clus_rnd_pos, clus_rnd_neg] = find_and_characterize_clusters(datrnd(indvec{:}));
    if ~isempty(clus_rnd_pos), null_pos(k) = max(clus_rnd_pos); end
    if ~isempty(clus_rnd_neg), null_neg(k) = min(clus_rnd_neg); end
end
null_pos = sort(null_pos(~isnan(null_pos)), 'descend');
null_neg = sort(null_neg(~isnan(null_neg)), 'ascend');

clus_p_pos = ones(size(clus_observed_pos));
for k = 1:numel(clus_observed_pos)
    clus_p_pos(k) = (sum(null_pos > clus_observed_pos(k)) + 1) / (numrnd+1);
end
clus_p_neg = ones(size(clus_observed_neg));
for k = 1:numel(clus_observed_neg)
    clus_p_neg(k) = (sum(null_neg < clus_observed_neg(k)) + 1) / (numrnd+1);
end

clusterinfo = [];
p = ones(size(datobs));
if tail >= 0
    for k = 1:numel(clus_p_pos)
        p(pos_inds{k}) = clus_p_pos(k);
        clusterinfo.pos_clusters(k).clusterstat = clus_observed_pos(k);
        clusterinfo.pos_clusters(k).p = clus_p_pos(k);
        clusterinfo.pos_clusters(k).inds = false(size(datobs));
        clusterinfo.pos_clusters(k).inds(pos_inds{k}) = 1;
        if tail == 0
            clusterinfo.pos_clusters(k).p = clusterinfo.pos_clusters(k).p * 2;
        end
    end
end
if tail <= 0
    for k = 1:numel(clus_p_neg)
        if clus_p_neg(k) < p(neg_inds{k}(1))
            p(neg_inds{k}) = clus_p_neg(k);
        end
        clusterinfo.neg_clusters(k).clusterstat = clus_observed_neg(k);
        clusterinfo.neg_clusters(k).p = clus_p_neg(k);
        clusterinfo.neg_clusters(k).inds = false(size(datobs));
        clusterinfo.neg_clusters(k).inds(neg_inds{k}) = 1;
        if tail == 0
            clusterinfo.neg_clusters(k).p = clusterinfo.neg_clusters(k).p * 2;
        end
    end
end
if tail == 0
    p = min(1, p .* 2);
end
h = p < alpha;

    function [clus_stats_pos, clus_stats_neg, pos_inds, neg_inds] = find_and_characterize_clusters(dat)
        if tail >= 0
            [clus_stats_pos, pos_inds] = compute_cluster_stats(dat, dat >= cluster_threshold_pos);
        end
        if tail <= 0
            [clus_stats_neg, neg_inds] = compute_cluster_stats(dat, dat <= cluster_threshold_neg);
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
