function out = qc_channels_from_tf(matfile, varargin)
% QC for TF z-power channels
% matfile: 'sub009_valence_TF_zpower.mat'
%
% Output:
%   out.tbl      : table of per-channel metrics sorted by badness
%   out.bad_ch   : suggested bad channel labels
%   out.good_ch  : suggested good channel labels
%   out.params   : parameters used

p = inputParser;
p.addParameter('z_extreme', 8);           % |z| >= this counted as extreme
p.addParameter('badscore_z', 3.5);        % robust z threshold on badness score
p.addParameter('max_nan_frac', 0.05);     % if NaN fraction > this -> likely bad
p.addParameter('max_extreme_frac', 0.01); % if extreme fraction > this -> likely bad
p.addParameter('plot_topk', 6);           % show top K worst + best
p.addParameter('use_freq_band', []);      % e.g., [1 150] or [] for all
p.addParameter('use_time_ms', []);        % e.g., [0 800] or [] for all
p.parse(varargin{:});
pr = p.Results;

S = load(matfile, '-mat');

mustHave = {'z_power_ds','chan_labels'};
for k = 1:numel(mustHave)
    assert(isfield(S, mustHave{k}), 'File missing variable: %s', mustHave{k});
end

Z = S.z_power_ds;              % [trial x chan x freq x time]
chan_labels = S.chan_labels(:);
nTr = size(Z,1); nCh = size(Z,2);
nF  = size(Z,3); nT  = size(Z,4);

% optional axes
if isfield(S,'freqs'); freqs = S.freqs(:); else; freqs = (1:nF)'; end
if isfield(S,'tms_ds'); tms = S.tms_ds(:); else; tms = (1:nT)'; end

% select freq/time
fsel = 1:nF;
tsel = 1:nT;

if ~isempty(pr.use_freq_band) && isfield(S,'freqs')
    [~, f1] = min(abs(freqs - pr.use_freq_band(1)));
    [~, f2] = min(abs(freqs - pr.use_freq_band(2)));
    fsel = f1:f2;
end

if ~isempty(pr.use_time_ms) && isfield(S,'tms_ds')
    [~, t1] = min(abs(tms - pr.use_time_ms(1)));
    [~, t2] = min(abs(tms - pr.use_time_ms(2)));
    tsel = t1:t2;
end

Z = Z(:,:,fsel,tsel);  % reduce
nF2 = numel(fsel); nT2 = numel(tsel);

% ===== metrics per channel =====
nan_frac      = nan(nCh,1);
extreme_frac  = nan(nCh,1);
mean_abs      = nan(nCh,1);
sd_overall    = nan(nCh,1);
mad_overall   = nan(nCh,1);
trial_drop    = nan(nCh,1); % fraction of trials with too many NaNs

z_ext = pr.z_extreme;

for ch = 1:nCh
    X = squeeze(Z(:,ch,:,:));               % [trial x f x t]
    x = X(:);
    nan_frac(ch) = mean(~isfinite(x));

    xok = x(isfinite(x));
    if isempty(xok)
        extreme_frac(ch) = 1;
        mean_abs(ch) = NaN;
        sd_overall(ch)  = NaN;
        mad_overall(ch) = NaN;
    else
        extreme_frac(ch) = mean(abs(xok) >= z_ext);
        mean_abs(ch)     = mean(abs(xok));
        sd_overall(ch)   = std(xok);
        mad_overall(ch)  = mad(xok, 1);     % median absolute deviation
    end

    % trial-level NaN issue: count trials with >20% NaN
    Xtr = reshape(X, nTr, []);
    tr_nan = mean(~isfinite(Xtr), 2);
    trial_drop(ch) = mean(tr_nan > 0.2);
end

% ===== combine into a single "badness score" =====
% robust-normalize each metric (median/MAD) and weight
M = [ ...
    nan_frac, ...
    extreme_frac, ...
    mean_abs, ...
    sd_overall, ...
    trial_drop ...
];

metric_names = {'nan_frac','extreme_frac','mean_abs','sd_overall','trial_drop'};

Zr = zeros(size(M));
for j = 1:size(M,2)
    v = M(:,j);
    medv = median(v, 'omitnan');
    madv = mad(v, 1);
    if madv == 0 || ~isfinite(madv)
        Zr(:,j) = (v - medv);
    else
        Zr(:,j) = (v - medv) / (madv + eps);
    end
end

% weights: NaN/extreme/trial_drop更“致命”，给高一点
w = [3, 3, 1.5, 1.5, 2.5];
bad_score = Zr * w(:);

% robust z of bad_score
bs_med = median(bad_score, 'omitnan');
bs_mad = mad(bad_score, 1);
bad_score_z = (bad_score - bs_med) / (bs_mad + eps);

% ===== suggested bad channels =====
is_bad = false(nCh,1);
is_bad = is_bad | (bad_score_z > pr.badscore_z);
is_bad = is_bad | (nan_frac > pr.max_nan_frac);
%is_bad = is_bad | (extreme_frac > pr.max_extreme_frac);
is_bad = is_bad | (trial_drop > 0.2);

tbl = table( ...
    chan_labels, ...
    bad_score, bad_score_z, ...
    nan_frac, extreme_frac, mean_abs, sd_overall, mad_overall, trial_drop, ...
    'VariableNames', { ...
        'ch', ...
        'bad_score','bad_z', ...
        'nan_frac','extreme_frac','mean_abs','sd_overall','mad_overall','trial_drop' ...
    } ...
);

tbl = sortrows(tbl, 'bad_score', 'descend');

out = struct();
out.tbl = tbl;
out.bad_ch  = chan_labels(is_bad);
out.good_ch = chan_labels(~is_bad);
out.params  = pr;

% ===== Print summary =====
fprintf('\n=== QC summary: %s ===\n', matfile);
fprintf('Trials=%d, Channels=%d, F=%d, T=%d (after selection)\n', nTr, nCh, nF2, nT2);
fprintf('Suggested bad channels: %d / %d\n', nnz(is_bad), nCh);

% show top lines
disp(tbl(1:min(12,height(tbl)), {'ch','bad_score','bad_z','nan_frac','extreme_frac','trial_drop'}));

% ===== Simple plots =====
figure('Name','Channel QC metrics','Position',[80 80 1200 520]);
subplot(1,3,1);
plot(tbl.bad_score, '-o'); xlabel('Channel (sorted worst->best)'); ylabel('bad score');
title('Badness score (sorted)'); grid on;

subplot(1,3,2);
plot(tbl.nan_frac, '-o'); hold on; yline(pr.max_nan_frac,'--');
xlabel('Channel (sorted)'); ylabel('NaN fraction'); title('NaN fraction'); grid on;

subplot(1,3,3);
plot(tbl.extreme_frac, '-o'); hold on; yline(pr.max_extreme_frac,'--');
xlabel('Channel (sorted)'); ylabel(sprintf('Frac(|z| >= %g)', z_ext));
title('Extreme fraction'); grid on;

% ===== Inspect topK worst and best mean TF =====
K = pr.plot_topk;
K = min(K, nCh);

% rebuild mean TF per channel for display
if isfield(S,'freqs'); freq_plot = S.freqs(fsel); else; freq_plot = 1:nF2; end
if isfield(S,'tms_ds'); t_plot = S.tms_ds(tsel); else; t_plot = 1:nT2; end

worst_labels = tbl.ch(1:K);
best_labels  = tbl.ch(end-K+1:end);

plot_channel_meanTF(S, worst_labels, fsel, tsel, freq_plot, t_plot, 'Worst channels (mean TF)');
plot_channel_meanTF(S, best_labels,  fsel, tsel, freq_plot, t_plot,  'Best channels (mean TF)');

end

% === helper: keep original order mapping ===
function idx = index_from_sorted(sorted_labels, original_labels)
% returns idx such that original_labels(idx) gives sorted_labels (if same set)
[~, idx] = ismember(sorted_labels, original_labels);
end

function plot_channel_meanTF(S, labels, fsel, tsel, freq_plot, t_plot, figTitle)
Z = S.z_power_ds;
chans = S.chan_labels(:);
nShow = numel(labels);
nCol = ceil(sqrt(nShow));
nRow = ceil(nShow / nCol);

figure('Name', figTitle, 'Position',[120 120 1200 700]);
for i = 1:nShow
    ch = find(strcmp(chans, labels{i}), 1);
    if isempty(ch), continue; end
    X = squeeze(Z(:,ch,fsel,tsel));    % [trial x f x t]
    m = squeeze(mean(X, 1, 'omitnan')); % [f x t]
    subplot(nRow,nCol,i);
    imagesc(t_plot, freq_plot, m); axis xy;
    title(strrep(labels{i},'_','\_'));
    xlabel('Time'); ylabel('Freq');
    colorbar;
end
sgtitle(figTitle);
end
