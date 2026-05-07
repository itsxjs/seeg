function run_LME_CBPT_valence()
%% ===== 基本参数 =====
% 这里列出你所有已经算好 valence TF 的被试
subs = {'sub001', 'sub004', 'sub005', 'sub007', 'sub008', 'sub009'};   % ← 修改成你自己的
data_dir = '/Users/defanive/Desktop/Diploma/seeg分析脚本scene';  % ← 放那些 subxxx_valence_TF_zpower.mat 的地方

% 如果想限定每个被试的通道，可以像下面这样写；不需要就留空 struct()
% subj_channels = struct();
% subj_channels.sub001 = {'A1-Ref','POL B1','C1-Ref','C2-Ref','C3-Ref'};
% subj_channels.sub004 = {'POL B1','POL B2','POL B3','POL B4','C2-Ref','C3-Ref','C4-Ref'};
% subj_channels.sub005 = {'POL B1','POL B2','POL L13','POL L14'};
% subj_channels.sub007 = {'POL B3','POL B4','C1-Ref','POL B1','POL B2','C2-Ref','C3-Ref','C4-Ref','F2-Ref','F3-Ref','F4-Ref'};
% subj_channels.sub008 = {'POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'};
% subj_channels.sub009 = {'POL B1','POL B2','POL B3'};
% % Hippocampus

subj_channels.sub001 = {'A2-Ref'};
subj_channels.sub004 = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
subj_channels.sub005 = {'A1-Ref','A2-Ref','POL A3','POL L7','POL L8','POL L9','POL L10'};
subj_channels.sub007 = {'A1-Ref','A2-Ref','POL A3','POL A4'};
subj_channels.sub008 = {'A1-Ref','A2-Ref','POL A3','POL A4','POL A5'};
subj_channels.sub009 = {'A1-Ref','A2-Ref','POL A3'};
% Amydgala

% 频率和时间轴都用文件里已有的
freq_band = [];     % 留空表示用全部频点
ds_ms     = [];     % 你文件里已经是下采样过的 tms_ds，就不用再下采

nperm = 1000;
rng(42);

% 并行池
if isempty(gcp('nocreate'))
    parpool('local');
end

%% ===== 读第一个被试拿轴 =====
first_file = fullfile(data_dir, sprintf('%s_valence_scene_TF_zpower.mat', subs{1}));
S0 = load_assert(first_file, ...
    {'z_power_ds','freqs','tms_ds','chan_labels','is_neg','is_pos'});
freqs = S0.freqs(:)';        % 1 × F
t_vec = S0.tms_ds(:)';       % 1 × T
nF_all = numel(freqs);
nT_all = numel(t_vec);

% 是否要裁频段
if ~isempty(freq_band)
    [~, f1] = min(abs(freqs - freq_band(1)));
    [~, f2] = min(abs(freqs - freq_band(2)));
    freq_sel = f1:f2;
else
    freq_sel = 1:nF_all;
end
freq_vec = freqs(freq_sel);
nF = numel(freq_sel);

% 时间这边，文件里已经是ds的了，就不再ds
t_keep = 1:nT_all;
nT = numel(t_keep);

fprintf('Freq: %d points, Time: %d points\n', nF, nT);

%% ===== 聚合所有被试的 trial × ch =====
Y_cell   = {};   % 每个元素是 [freq × time]
sid_cell = {};
ch_cell  = {};
val_cell = {};   % 'neg' or 'pos'

for isub = 1:numel(subs)
    sid = subs{isub};
    infile = fullfile(data_dir, sprintf('%s_valence_scene_TF_zpower.mat', sid));
    S = load_assert(infile, ...
        {'z_power_ds','freqs','tms_ds','chan_labels','is_neg','is_pos'});
    
    zpow   = S.z_power_ds;       % [trial × chan × freq × time] = [116 × 78 × 24 × 40]
    chans  = S.chan_labels;
    is_neg = S.is_neg(:);
    is_pos = S.is_pos(:);

    % 选通道（如果有的话）
    if isfield(subj_channels, sid)
        keep_ch = ismember(chans, subj_channels.(sid));
    else
        keep_ch = true(1, numel(chans));
    end
    
    % 我们只分析 neg 和 pos，neu 直接跳过
    use_trials = find(is_neg | is_pos);
    
    for ch = find(keep_ch)
        for tr = use_trials'
            % 取出这个 trial 的 freq×time
            patch = squeeze(zpow(tr, ch, freq_sel, t_keep));  % [nF × nT]
            if numel(patch)==nF*nT
                Y_cell{end+1,1}   = patch;
                sid_cell{end+1,1} = sid;
                ch_cell{end+1,1}  = chans{ch};
                if is_neg(tr)
                    val_cell{end+1,1} = 'neg';
                else
                    val_cell{end+1,1} = 'pos';
                end
            end
        end
    end
end

% 合并
Y = cat(3, Y_cell{:});     % [nF × nT × nRows]
Y = permute(Y, [3 1 2]);   % [nRows × nF × nT]
nRows = size(Y,1);

base_tbl = table( ...
    categorical(sid_cell), ...
    categorical(ch_cell), ...
    categorical(val_cell), ...
    'VariableNames', {'sid','ch','valence'});

fprintf('Collected %d observations (trial×channel)\n', nRows);

%% ===== 先算两个条件的平均，方便看方向 =====
avg_val.neg = nan(nF,nT);
avg_val.pos = nan(nF,nT);
for f = 1:nF
    for t = 1:nT
        y = Y(:,f,t);
        ok = isfinite(y);
        idx_neg = ok & base_tbl.valence=="neg";
        idx_pos = ok & base_tbl.valence=="pos";
        if any(idx_neg), avg_val.neg(f,t) = mean(y(idx_neg)); end
        if any(idx_pos), avg_val.pos(f,t) = mean(y(idx_pos)); end
    end
end
diff_map = avg_val.pos - avg_val.neg;  % >0 说明 positive 条件z更高

%% ===== 逐 freq×time 做 LME: data ~ valence + (1|sid) + (1|sid:ch) =====
F_val = nan(nF,nT);
P_val = nan(nF,nT);

fprintf('Fitting LME per freq-time (%d × %d)...\n', nF, nT);

parfor f = 1:nF
    F_f = nan(1,nT);
    P_f = nan(1,nT);
    for t = 1:nT
        y = Y(:,f,t);
        ok = isfinite(y);
        if nnz(ok) < 20, continue; end   % 太少就跳过
        
        T = table( ...
            categorical(base_tbl.sid(ok)), ...
            categorical(base_tbl.ch(ok)), ...
            categorical(base_tbl.valence(ok)), ...
            double(y(ok)), ...
            'VariableNames', {'sid','ch','valence','data'});
        try
            mdl = fitlme(T, 'data ~ valence + (1|sid) + (1|sid:ch)', ...
                            'FitMethod','REML','DummyVarCoding','effects');
            A = anova(mdl);
            % anova行一般是: (Intercept), valence
            F_f(t) = A.FStat(2);
            P_f(t) = A.pValue(2);
        catch ME
            warning('LME fail f=%d,t=%d: %s',f,t,ME.message);
        end
    end
    F_val(f,:) = F_f;
    P_val(f,:) = P_f;
end

%% ===== 做置换：组内打乱标签 =====
fprintf('Permutations n=%d ...\n', nperm);

uid = strcat(string(base_tbl.sid), "_", string(base_tbl.ch));
grp = findgroups(uid);
G = unique(grp)';

F_null = zeros(nF, nT, nperm);

parfor pp = 1:nperm
    val_perm = base_tbl.valence;
    % 在每个被试×通道内打乱 neg/pos
    for g = G
        idx = find(grp==g);
        if numel(idx)>1
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
            T = table( ...
                categorical(base_tbl.sid(ok)), ...
                categorical(base_tbl.ch(ok)), ...
                categorical(val_perm(ok)), ...
                double(y(ok)), ...
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

%% ===== 2D cluster-based permutation test =====
fprintf('Cluster-based correction...\n');
[h_val, p_val_clust, clusterinfo_val] = cluster_test(F_val, F_null, 1);

%% ===== 保存 =====
res = struct();
res.subs      = subs;
res.freq_vec  = freq_vec;
res.t_vec     = t_vec;
res.F_val     = F_val;
res.P_val     = P_val;
res.P_val_clust = p_val_clust;
res.h_val     = h_val;
res.clusterinfo_val = clusterinfo_val;
res.avg_val   = avg_val;
res.diff_map  = diff_map;
res.nperm     = nperm;

out_name = fullfile(data_dir, 'LME_Amydgala_CBPT_2D_valence_FreqTime.mat');
save(out_name, 'res','-v7.3');
fprintf('✔ Saved -> %s\n', out_name);

%% ===== 画图 =====
plot_valence_results(res, data_dir);

fprintf('\n== DONE: valence (neg vs pos) ==\n');
end


%%  ===== 画图函数（valence, 正确处理非均匀频率轴） =====
function plot_valence_results(res, data_dir)

freq_vec = res.freq_vec;
t_vec    = res.t_vec;
[TT, FF] = meshgrid(t_vec, freq_vec);

tf_xlabel = '时间 (ms)';
tf_ylabel = '频率 (Hz)';

%% ================= 图1: F-stat + 显著簇 =================
fig1 = figure('Position',[100 100 1200 500]);

% --- (1) LME F-stat ---
subplot(1,3,1);
surf(TT, FF, res.F_val, 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, hot);
xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('效价效应：线性混合模型F值', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);

% --- (2) cluster p ---
subplot(1,3,2);
p_plot = res.P_val_clust;
p_plot(p_plot==0) = min(p_plot(p_plot>0))/10;

surf(TT, FF, -log10(p_plot), 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, parula);
xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('簇校正p值 (-log10)', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);

% --- (3) F-stat + sig clusters ---
subplot(1,3,3);
surf(TT, FF, res.F_val, 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, hot);
hold on;

if any(res.h_val(:))
    z0 = max(res.F_val(:), [], 'omitnan') + 1e-6;
    BW = res.h_val > 0;
    B  = bwboundaries(BW, 'noholes');

    for k = 1:numel(B)
        pix = B{k};
        f_idx = pix(:,1);
        t_idx = pix(:,2);
        plot3(t_vec(t_idx), freq_vec(f_idx), ...
              z0*ones(size(f_idx)), ...
              'c', 'LineWidth', 2);
    end
    set(gca,'Clipping','off');
end

xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('F值与显著簇 (p<0.05)', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);
sgtitle('情绪效价效应：正性与负性图片比较', 'FontSize', 16, 'FontWeight', 'bold');

saveas(fig1, fullfile(data_dir, 'LME_Amydgala_CBPT_2D_valence_FreqTime_Fstats.png'));
fprintf('✔ Figure saved: LME_Amydgala_CBPT_2D_valence_FreqTime_Fstats.png\n');


%% ================= 图2: 条件均值 =================
fig2 = figure('Position',[150 150 1200 500]);

% --- (1) negative ---
subplot(1,3,1);
surf(TT, FF, res.avg_val.neg, 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, jet);
xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('负性图片：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);

% --- (2) positive ---
subplot(1,3,2);
surf(TT, FF, res.avg_val.pos, 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, jet);
xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('正性图片：平均z功率', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);

% --- (3) pos - neg + cluster ---
subplot(1,3,3);
surf(TT, FF, res.diff_map, 'EdgeColor','none');
view(2);
set(gca,'YScale','log');
axis tight; colorbar; colormap(gca, redblue);
hold on;

if any(res.h_val(:))
    z0 = max(res.diff_map(:), [], 'omitnan') + 1e-6;
    BW = res.h_val > 0;
    B  = bwboundaries(BW, 'noholes');

    for k = 1:numel(B)
        pix = B{k};
        f_idx = pix(:,1);
        t_idx = pix(:,2);
        plot3(t_vec(t_idx), freq_vec(f_idx), ...
              z0*ones(size(f_idx)), ...
              'k', 'LineWidth', 2);
    end
    set(gca,'Clipping','off');
end

xlabel(tf_xlabel, 'FontSize', 13); ylabel(tf_ylabel, 'FontSize', 13);
title('正性 - 负性 (方向差异)', 'FontSize', 14, 'FontWeight', 'bold');
set(gca, 'FontSize', 12, 'LineWidth', 1);

saveas(fig2, fullfile(data_dir, 'LME_Amydgala_CBPT_2D_valence_FreqTime_Averages.png'));
fprintf('✔ Figure saved: LME_Amydgala_CBPT_2D_valence_FreqTime_Averages.png\n');

% 打印簇信息
if isfield(res,'clusterinfo_val') && isfield(res.clusterinfo_val,'pos_clusters')
    fprintf('\n== Significant clusters (valence) ==\n');
    ci = res.clusterinfo_val;
    for k = 1:numel(ci.pos_clusters)
        if ci.pos_clusters(k).p < 0.05
            mask = ci.pos_clusters(k).inds;
            [fi, ti] = find(mask);
            fprintf('  Cluster %d: p=%.4f, size=%d\n', ...
                k, ci.pos_clusters(k).p, nnz(mask));
            fprintf('    Freq: %.2f - %.2f Hz\n', ...
                min(freq_vec(fi)), max(freq_vec(fi)));
            fprintf('    Time: %.1f - %.1f ms\n', ...
                min(t_vec(ti)), max(t_vec(ti)));
            % 看一下方向
            mean_diff = mean(res.diff_map(mask),'omitnan');
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
