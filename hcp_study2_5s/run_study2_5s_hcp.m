function run_study2_5s_hcp(cfg)
%% Study 2 5-s TF + LME/CBPT runner for HPC MATLAB.
% Put this file, BOSC_tf_power.m, the *_rate_preproc.set/.fdt files,
% and the 2-s *_4bin_epoch_clean.set files under seeg_xjs. Then run:
%   run_study2_5s_hcp

%% ===== User-editable paths =====
if nargin < 1 || isempty(cfg)
    cfg = struct();
end

this_dir = fileparts(mfilename('fullpath'));
project_dir = get_cfg(cfg, 'project_dir', '/public/home/u0018083/seeg_xjs');
data_dir = get_cfg(cfg, 'data_dir', project_dir);
eeglab_dir = get_cfg(cfg, 'eeglab_dir', '/public/home/u0018083/sEEG_Chenglu/EEGLAB');
subs = get_cfg(cfg, 'subs', {'sub001', 'sub004', 'sub005', 'sub007', 'sub008', 'sub009'});

% HPC settings requested by the advisor.
nperm = get_cfg(cfg, 'nperm', 1000);
n_workers = get_cfg(cfg, 'n_workers', 16);
rng_seed = get_cfg(cfg, 'rng_seed', 42);

% TF settings for the 5-s study-2 window.
baseline_win = get_cfg(cfg, 'baseline_win', [-500 0]);    % ms
analysis_win = get_cfg(cfg, 'analysis_win', [0 5000]);    % ms
epoch_win = get_cfg(cfg, 'epoch_win', [-0.5 5]);          % s
freqs = get_cfg(cfg, 'freqs', logspace(log10(2), log10(120), 24));
tf_bootstrap_n = get_cfg(cfg, 'tf_bootstrap_n', 1000);
ds_ms = get_cfg(cfg, 'ds_ms', 50);
force_recompute_tf = get_cfg(cfg, 'force_recompute_tf', true);

%% ===== Init =====
clc;
rng(rng_seed);
addpath(this_dir);
init_eeglab(eeglab_dir);
ensure_pool(n_workers);

%% ===== Step 1: create 5-s TF files =====
for isub = 1:numel(subs)
    sid = subs{isub};
    out_file = fullfile(data_dir, sprintf('%s_valence_BOSC_TF_zpower_5s.mat', sid));
    if isfile(out_file) && ~force_recompute_tf
        fprintf('[%s] TF file exists, skip: %s\n', sid, out_file);
        continue;
    elseif isfile(out_file) && force_recompute_tf
        fprintf('[%s] TF file exists but force_recompute_tf=true, overwrite: %s\n', sid, out_file);
    end

    fprintf('\n[%s] Creating 5-s TF file...\n', sid);
    compute_subject_tf_5s(data_dir, sid, epoch_win, baseline_win, analysis_win, ...
        freqs, tf_bootstrap_n, ds_ms, out_file);
end

%% ===== Step 2: run ROI-level LME/CBPT =====
roi_defs = build_roi_defs();
for r = 1:numel(roi_defs)
    fprintf('\n== Running ROI: %s ==\n', roi_defs(r).label);
    res = run_roi_lme_cbpt(data_dir, subs, roi_defs(r), nperm);
    out_name = fullfile(data_dir, sprintf('LME_%s_CBPT_2D_like_dislike_FreqTime_5s_nperm%d.mat', ...
        roi_defs(r).prefix, nperm));
    save(out_name, 'res', 'subs', 'nperm', '-v7.3');
    fprintf('Saved MAT -> %s\n', out_name);
    plot_like_dislike_results(res, data_dir, roi_defs(r).prefix, nperm);
end

fprintf('\nDONE: Study 2 5-s window, nperm=%d, parpool=%d.\n', nperm, n_workers);
end

function value = get_cfg(cfg, field, default_value)
if isfield(cfg, field) && ~isempty(cfg.(field))
    value = cfg.(field);
else
    value = default_value;
end
end

function init_eeglab(eeglab_dir)
if ~isempty(eeglab_dir)
    assert(isfolder(eeglab_dir), 'EEGLAB folder not found: %s', eeglab_dir);
    addpath(genpath(eeglab_dir));
end

if exist('eeglab', 'file') == 2
    eeglab nogui;
elseif exist('pop_loadset', 'file') ~= 2
    error(['EEGLAB is required to read .set/.fdt files. Upload EEGLAB and set ', ...
        'eeglab_dir near the top of this script.']);
end
end

function ensure_pool(n_workers)
pool = gcp('nocreate');
if isempty(pool)
    parpool('local', n_workers);
elseif pool.NumWorkers ~= n_workers
    delete(pool);
    parpool('local', n_workers);
end
end

function compute_subject_tf_5s(data_dir, sid, epoch_win, baseline_win, analysis_win, ...
    freqs, n_bs, ds_ms, out_file)

clean_file = fullfile(data_dir, sprintf('%s_4bin_epoch_clean.set', sid));
assert(isfile(clean_file), ['[%s] Missing 2-s clean epoch file: %s\n', ...
    'Upload this file so the 5-s run inherits the exact 2-s QC trial whitelist.'], sid, clean_file);

EEG_clean = pop_loadset('filename', sprintf('%s_4bin_epoch_clean.set', sid), 'filepath', data_dir);
clean_keys = extract_clean_trial_keys(EEG_clean);
fprintf('[%s] Loaded 2-s QC whitelist: %d clean preference trials\n', sid, numel(clean_keys.label));

in_candidates = { ...
    sprintf('%s_rate_preproc.set', sid), ...
    sprintf('%s_rate.set', sid) ...
};

EEG = [];
for k = 1:numel(in_candidates)
    fn = fullfile(data_dir, in_candidates{k});
    if isfile(fn)
        EEG = pop_loadset('filename', in_candidates{k}, 'filepath', data_dir);
        fprintf('[%s] Loaded continuous file: %s\n', sid, in_candidates{k});
        break;
    end
end
if isempty(EEG)
    error('[%s] Cannot find %s or %s in %s', sid, in_candidates{1}, in_candidates{2}, data_dir);
end

EEG = append_preference_events(EEG, epoch_win, clean_keys);
EEG = pop_epoch(EEG, {'dislike', 'neutral', 'like'}, epoch_win);
EEG = eeg_checkset(EEG);

srate = EEG.srate;
n_trials = EEG.trials;
n_chans = EEG.nbchan;
tms = EEG.times;

is_dislike = false(n_trials, 1);
is_like = false(n_trials, 1);
trial_qc_key = strings(n_trials, 1);
for tr = 1:n_trials
    types = epoch_event_types(EEG.epoch(tr).eventtype);
    is_dislike(tr) = any(types == "dislike");
    is_like(tr) = any(types == "like");
    trial_qc_key(tr) = epoch_qc_key(EEG.epoch(tr));
end

if n_trials ~= numel(clean_keys.label)
    warning('[%s] 5-s available trials (%d) differ from 2-s QC whitelist (%d). This usually means some QC-passed trials are too close to file end for a full 5-s window.', ...
        sid, n_trials, numel(clean_keys.label));
end

time_idx = find(tms >= analysis_win(1) & tms <= analysis_win(2));
baseline_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
if isempty(time_idx) || isempty(baseline_idx)
    error('[%s] baseline_win or analysis_win is outside the epoch range.', sid);
end

nyq = srate / 2;
freqs = freqs(freqs < nyq - 1e-6);
n_freqs = numel(freqs);
num_cycles = logspace(log10(3), log10(12), n_freqs);

power_data = zeros(n_trials, n_chans, n_freqs, numel(time_idx), 'single');
base_power_data = zeros(n_trials, n_chans, n_freqs, numel(baseline_idx), 'single');

fprintf('[%s] Wavelet power: trials=%d, channels=%d, freqs=%d, time=%d samples\n', ...
    sid, n_trials, n_chans, n_freqs, numel(time_idx));

for tr = 1:n_trials
    if mod(tr, 10) == 0 || tr == n_trials
        fprintf('[%s]   trial %d/%d\n', sid, tr, n_trials);
    end
    for ch = 1:n_chans
        x = double(EEG.data(ch, :, tr));
        B = zeros(n_freqs, numel(x));
        for fi = 1:n_freqs
            B(fi, :) = BOSC_tf_power(x, freqs(fi), srate, num_cycles(fi));
        end
        power_data(tr, ch, :, :) = single(B(:, time_idx));
        base_power_data(tr, ch, :, :) = single(B(:, baseline_idx));
    end
end

z_power = zeros(size(power_data), 'single');
mu_baseline = zeros(n_chans, n_freqs, 'single');
sigma_baseline = zeros(n_chans, n_freqs, 'single');

for ch = 1:n_chans
    for f = 1:n_freqs
        base_vals = squeeze(base_power_data(:, ch, f, :));
        base_all = base_vals(:);
        base_all = base_all(isfinite(base_all));
        if isempty(base_all)
            base_all = 0;
        end

        null_distr = zeros(n_bs, 1);
        for b = 1:n_bs
            sample_idx = randi(numel(base_all), [n_trials, 1]);
            null_distr(b) = mean(base_all(sample_idx));
        end
        mu = mean(null_distr);
        sg = std(null_distr);
        if ~isfinite(sg) || sg <= eps
            sg = 1;
        end

        mu_baseline(ch, f) = mu;
        sigma_baseline(ch, f) = sg;
        z_power(:, ch, f, :) = (power_data(:, ch, f, :) - mu) ./ sg;
    end
end

dt = mean(diff(tms));
ds_factor = max(1, round(ds_ms / dt));
sel_idx = 1:ds_factor:numel(time_idx);

z_power_ds = z_power(:, :, :, sel_idx);
tms_ds = tms(time_idx);
tms_ds = tms_ds(sel_idx);
chan_labels = {EEG.chanlocs.labels};
cond_labels = {'dislike', 'like'};
cond_mask = {is_dislike, is_like};
cond_mean_z = nan(2, n_chans, n_freqs, numel(sel_idx), 'single');
cond_n = zeros(2, 1);

for c = 1:2
    mask = cond_mask{c};
    if any(mask)
        cond_mean_z(c, :, :, :) = squeeze(mean(z_power_ds(mask, :, :, :), 1, 'omitnan'));
        cond_n(c) = sum(mask);
    end
end

meta = struct();
meta.sid = sid;
meta.epoch_win_s = epoch_win;
meta.baseline_win_ms = baseline_win;
meta.analysis_win_ms = analysis_win;
meta.freqs = freqs;
meta.tf_bootstrap_n = n_bs;
meta.ds_ms = ds_ms;
meta.method = 'BOSC Morlet power, baseline bootstrap z-score';

save(out_file, 'z_power_ds', 'freqs', 'tms_ds', 'mu_baseline', 'sigma_baseline', ...
    'chan_labels', 'cond_labels', 'cond_mean_z', 'cond_n', 'is_dislike', 'is_like', ...
    'trial_qc_key', 'meta', '-v7.3');
fprintf('[%s] Saved TF -> %s\n', sid, out_file);
end

function clean_keys = extract_clean_trial_keys(EEG_clean)
n_tr = EEG_clean.trials;
labels = strings(n_tr, 1);
keys = strings(n_tr, 1);
for tr = 1:n_tr
    ep = EEG_clean.epoch(tr);
    types = epoch_event_types(ep.eventtype);
    zero_idx = epoch_zero_event_indices(ep);
    label = "";
    key = "";
    for ii = zero_idx
        lab = rating_to_label(types(ii));
        if lab == "dislike" || lab == "neutral" || lab == "like"
            label = lab;
            key = make_epoch_event_key(ep, ii);
            break;
        end
    end
    if label == ""
        for ii = 1:numel(types)
            lab = rating_to_label(types(ii));
            if lab == "dislike" || lab == "neutral" || lab == "like"
                label = lab;
                key = make_epoch_event_key(ep, ii);
                break;
            end
        end
    end
    labels(tr) = label;
    keys(tr) = key;
end

keep = labels == "dislike" | labels == "neutral" | labels == "like";
clean_keys.label = labels(keep);
clean_keys.key = keys(keep);
clean_keys.keyset = unique(keys(keep));
if any(startsWith(clean_keys.keyset, "rel"))
    error(['The 2-s clean epoch file does not expose usable eventurevent IDs. ', ...
        'Cannot safely align 5-s epochs to the 2-s QC whitelist.']);
end
end

function idx = epoch_zero_event_indices(ep)
lat = ep.eventlatency;
if iscell(lat)
    vals = cellfun(@double, lat);
else
    vals = double(lat);
end
idx = find(abs(vals) < 1e-6);
if isempty(idx)
    idx = 1:numel(vals);
end
end

function key = make_epoch_event_key(ep, idx)
urevent = [];
if isfield(ep, 'eventurevent')
    eu = ep.eventurevent;
    if iscell(eu)
        urevent = double(eu{idx});
    else
        urevent = double(eu(idx));
    end
end

lat = ep.eventlatency;
if iscell(lat)
    rel_lat = double(lat{idx});
else
    rel_lat = double(lat(idx));
end

if ~isempty(urevent) && isfinite(urevent)
    key = "u" + string(round(urevent));
else
    key = "rel" + string(round(rel_lat));
end
end

function key = make_continuous_event_key(ev)
if isfield(ev, 'urevent') && ~isempty(ev.urevent) && isfinite(double(ev.urevent))
    key = "u" + string(round(double(ev.urevent)));
else
    key = "lat" + string(round(double(ev.latency)));
end
end

function key = epoch_qc_key(ep)
zero_idx = epoch_zero_event_indices(ep);
key = "";
for ii = zero_idx
    types = epoch_event_types(ep.eventtype);
    lab = rating_to_label(types(ii));
    if lab == "dislike" || lab == "neutral" || lab == "like"
        key = make_epoch_event_key(ep, ii);
        return;
    end
end
if key == ""
    key = make_epoch_event_key(ep, zero_idx(1));
end
end

function EEG = append_preference_events(EEG, epoch_win, clean_keys)
srate = EEG.srate;
pre_samp = round(abs(epoch_win(1)) * srate);
post_samp = round(epoch_win(2) * srate);
new_events = EEG.event;
add_count = 0;
skip_count = 0;
not_in_qc_count = 0;

for i = 1:numel(EEG.event)
    key = make_continuous_event_key(EEG.event(i));
    key_idx = find(clean_keys.key == key, 1, 'first');
    if isempty(key_idx)
        not_in_qc_count = not_in_qc_count + 1;
        continue;
    end
    lab = clean_keys.label(key_idx);

    lat = EEG.event(i).latency;
    if (lat - pre_samp < 1) || (lat + post_samp > EEG.pnts)
        skip_count = skip_count + 1;
        continue;
    end

    e2 = EEG.event(i);
    e2.type = char(lab);
    e2.latency = lat;
    new_events(end + 1) = e2; %#ok<AGROW>
    add_count = add_count + 1;
end

EEG.event = new_events;
EEG = eeg_checkset(EEG, 'eventconsistency');
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');
fprintf('Added QC-passed preference events: %d; skipped by 2-s QC whitelist: %d; skipped for insufficient 5-s window: %d\n', ...
    add_count, not_in_qc_count, skip_count);
if add_count == 0
    error('No events matched the 2-s QC whitelist. Check that *_rate_preproc.set and *_4bin_epoch_clean.set come from the same preprocessing run.');
end
end

function s = normalize_event_type(x)
if isnumeric(x)
    s = string(x);
elseif isstring(x)
    s = x;
elseif ischar(x)
    s = string(strtrim(x));
else
    s = "";
end
end

function lab = rating_to_label(etype)
if etype == "1" || etype == "2"
    lab = "dislike";
elseif etype == "3"
    lab = "neutral";
elseif etype == "4" || etype == "5"
    lab = "like";
elseif etype == "dislike" || etype == "neutral" || etype == "like"
    lab = etype;
else
    lab = "";
end
end

function types = epoch_event_types(et)
if iscell(et)
    types = string(et);
else
    types = string({et});
end
types = strtrim(types);
end

function roi_defs = build_roi_defs()
roi_defs(1).label = 'Amygdala';
roi_defs(1).prefix = 'Amydgala';
roi_defs(1).channels.sub001 = {'A2-Ref'};
roi_defs(1).channels.sub004 = {'A1-Ref', 'A2-Ref', 'POL A3', 'POL A4', 'POL A5'};
roi_defs(1).channels.sub005 = {'A1-Ref', 'A2-Ref', 'POL A3', 'POL L7', 'POL L8', 'POL L9', 'POL L10'};
roi_defs(1).channels.sub007 = {'A1-Ref', 'A2-Ref', 'POL A3', 'POL A4'};
roi_defs(1).channels.sub008 = {'A1-Ref', 'A2-Ref', 'POL A3', 'POL A4', 'POL A5'};
roi_defs(1).channels.sub009 = {'A1-Ref', 'A2-Ref', 'POL A3'};

roi_defs(2).label = 'Hippocampus';
roi_defs(2).prefix = 'Hippocampus';
roi_defs(2).channels.sub001 = {'A1-Ref', 'POL B1', 'C1-Ref', 'C2-Ref', 'C3-Ref'};
roi_defs(2).channels.sub004 = {'POL B1', 'POL B2', 'POL B3', 'POL B4', 'C2-Ref', 'C3-Ref', 'C4-Ref'};
roi_defs(2).channels.sub005 = {'POL B1', 'POL B2', 'POL L13', 'POL L14'};
roi_defs(2).channels.sub007 = {'POL B3', 'POL B4', 'C1-Ref', 'POL B1', 'POL B2', 'C2-Ref', 'C3-Ref', 'C4-Ref', 'F2-Ref', 'F3-Ref', 'F4-Ref'};
roi_defs(2).channels.sub008 = {'POL B1', 'POL B2', 'C1-Ref', 'C2-Ref', 'C3-Ref'};
roi_defs(2).channels.sub009 = {'POL B1', 'POL B2', 'POL B3'};
end

function res = run_roi_lme_cbpt(data_dir, subs, roi_def, nperm)
first_file = fullfile(data_dir, sprintf('%s_valence_BOSC_TF_zpower_5s.mat', subs{1}));
S0 = load_assert(first_file, {'z_power_ds', 'freqs', 'tms_ds', 'chan_labels', 'is_like', 'is_dislike'});
freq_vec = S0.freqs(:)';
t_vec = S0.tms_ds(:)';
nF = numel(freq_vec);
nT = numel(t_vec);

Y_cell = {};
sid_cell = {};
ch_cell = {};
pref_cell = {};

for isub = 1:numel(subs)
    sid = subs{isub};
    infile = fullfile(data_dir, sprintf('%s_valence_BOSC_TF_zpower_5s.mat', sid));
    S = load_assert(infile, {'z_power_ds', 'freqs', 'tms_ds', 'chan_labels', 'is_like', 'is_dislike'});

    zpow = S.z_power_ds;
    chans = S.chan_labels;
    is_like = S.is_like(:);
    is_dislike = S.is_dislike(:);

    if isfield(roi_def.channels, sid)
        keep_ch = ismember(chans, roi_def.channels.(sid));
    else
        keep_ch = true(1, numel(chans));
    end

    missing = setdiff(roi_def.channels.(sid), chans);
    if ~isempty(missing)
        fprintf('[%s/%s] Missing channels ignored: %s\n', sid, roi_def.label, strjoin(missing, ', '));
    end

    use_trials = find(is_like | is_dislike);
    n_keep_ch = nnz(keep_ch);
    n_like_trials = nnz(is_like(use_trials));
    n_dislike_trials = nnz(is_dislike(use_trials));
    fprintf('[%s/%s] ROI channels kept=%d, trials dislike=%d, like=%d, observations dislike=%d, like=%d\n', ...
        sid, roi_def.label, n_keep_ch, n_dislike_trials, n_like_trials, ...
        n_dislike_trials * n_keep_ch, n_like_trials * n_keep_ch);

    for ch = find(keep_ch)
        for tr = use_trials'
            patch = squeeze(zpow(tr, ch, :, :));
            if numel(patch) == nF * nT
                Y_cell{end + 1, 1} = patch; %#ok<AGROW>
                sid_cell{end + 1, 1} = sid; %#ok<AGROW>
                ch_cell{end + 1, 1} = chans{ch}; %#ok<AGROW>
                if is_like(tr)
                    pref_cell{end + 1, 1} = 'like'; %#ok<AGROW>
                else
                    pref_cell{end + 1, 1} = 'dislike'; %#ok<AGROW>
                end
            end
        end
    end
end

Y = cat(3, Y_cell{:});
Y = permute(Y, [3 1 2]);
nRows = size(Y, 1);
base_tbl = table(categorical(sid_cell), categorical(ch_cell), categorical(pref_cell), ...
    'VariableNames', {'sid', 'ch', 'preference'});

total_dislike = nnz(base_tbl.preference == "dislike");
total_like = nnz(base_tbl.preference == "like");
fprintf('[%s] Collected %d observations (trial x channel), F=%d, T=%d\n', ...
    roi_def.label, nRows, nF, nT);
fprintf('[%s] Condition observations: dislike=%d, like=%d\n', roi_def.label, total_dislike, total_like);
if total_dislike == 0 || total_like == 0
    warning('[%s] One condition has zero observations after ROI channel selection. The corresponding average/difference plot will be blank.', roi_def.label);
end

avg_pref.dislike = nan(nF, nT);
avg_pref.like = nan(nF, nT);
for f = 1:nF
    for t = 1:nT
        y = Y(:, f, t);
        ok = isfinite(y);
        idx_dislike = ok & base_tbl.preference == "dislike";
        idx_like = ok & base_tbl.preference == "like";
        if any(idx_dislike)
            avg_pref.dislike(f, t) = mean(y(idx_dislike));
        end
        if any(idx_like)
            avg_pref.like(f, t) = mean(y(idx_like));
        end
    end
end
diff_map = avg_pref.like - avg_pref.dislike;

F_pref = nan(nF, nT);
P_pref = nan(nF, nT);
fprintf('[%s] Fitting observed LME grid...\n', roi_def.label);

parfor f = 1:nF
    F_f = nan(1, nT);
    P_f = nan(1, nT);
    for t = 1:nT
        y = Y(:, f, t);
        ok = isfinite(y);
        if nnz(ok) < 20
            continue;
        end
        T = table(categorical(base_tbl.sid(ok)), categorical(base_tbl.ch(ok)), ...
            categorical(base_tbl.preference(ok)), double(y(ok)), ...
            'VariableNames', {'sid', 'ch', 'preference', 'data'});
        try
            mdl = fitlme(T, 'data ~ preference + (1|sid) + (1|sid:ch)', ...
                'FitMethod', 'REML', 'DummyVarCoding', 'effects');
            A = anova(mdl);
            F_f(t) = A.FStat(2);
            P_f(t) = A.pValue(2);
        catch
        end
    end
    F_pref(f, :) = F_f;
    P_pref(f, :) = P_f;
end

if nperm > 0
    fprintf('[%s] Permutations n=%d...\n', roi_def.label, nperm);
    uid = strcat(string(base_tbl.sid), "_", string(base_tbl.ch));
    grp = findgroups(uid);
    G = unique(grp)';
    F_null = zeros(nF, nT, nperm);

    parfor pp = 1:nperm
        pref_perm = base_tbl.preference;
        stream = RandStream('Threefry', 'Seed', 100000 + pp);
        for g = G
            idx = find(grp == g);
            if numel(idx) > 1
                ord = randperm(stream, numel(idx));
                pref_perm(idx) = pref_perm(idx(ord));
            end
        end

        F_pp = nan(nF, nT);
        for f = 1:nF
            for t = 1:nT
                y = Y(:, f, t);
                ok = isfinite(y);
                if nnz(ok) < 20
                    continue;
                end
                T = table(categorical(base_tbl.sid(ok)), categorical(base_tbl.ch(ok)), ...
                    categorical(pref_perm(ok)), double(y(ok)), ...
                    'VariableNames', {'sid', 'ch', 'preference', 'data'});
                try
                    mdlp = fitlme(T, 'data ~ preference + (1|sid) + (1|sid:ch)', ...
                        'FitMethod', 'REML', 'DummyVarCoding', 'effects');
                    Ap = anova(mdlp);
                    F_pp(f, t) = Ap.FStat(2);
                catch
                end
            end
        end
        F_null(:, :, pp) = F_pp;
    end

    fprintf('[%s] Cluster correction...\n', roi_def.label);
    [h_pref, p_pref_clust, clusterinfo_pref] = cluster_test(F_pref, F_null, 1);
else
    fprintf('[%s] nperm=0, skip permutations and cluster correction.\n', roi_def.label);
    h_pref = false(nF, nT);
    p_pref_clust = ones(nF, nT);
    clusterinfo_pref = struct();
end

res = struct();
res.roi = roi_def.label;
res.roi_prefix = roi_def.prefix;
res.subs = subs;
res.freq_vec = freq_vec;
res.t_vec = t_vec;
res.F_pref = F_pref;
res.P_pref = P_pref;
res.P_pref_clust = p_pref_clust;
res.h_pref = h_pref;
res.clusterinfo_pref = clusterinfo_pref;
res.avg_pref = avg_pref;
res.diff_map = diff_map;
res.nperm = nperm;
res.nRows = nRows;
end

function plot_like_dislike_results(res, data_dir, roi_prefix, nperm)
freq_vec = res.freq_vec;
t_vec = res.t_vec;
[TT, FF] = meshgrid(t_vec, freq_vec);

fig1 = figure('Position', [100 100 1200 500], 'Visible', 'off');
subplot(1, 3, 1);
surf(TT, FF, res.F_pref, 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, hot);
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('LME F');

subplot(1, 3, 2);
p_plot = res.P_pref_clust;
if any(p_plot(:) > 0)
    p_plot(p_plot == 0) = min(p_plot(p_plot > 0)) / 10;
end
surf(TT, FF, -log10(p_plot), 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, parula);
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('Cluster p (-log10)');

subplot(1, 3, 3);
surf(TT, FF, res.F_pref, 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, hot);
hold on;
draw_cluster_boundaries(res.h_pref, t_vec, freq_vec, max(res.F_pref(:), [], 'omitnan') + 1e-6, 'c');
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('F with significant clusters');
sgtitle(sprintf('%s like vs dislike, 5 s, nperm=%d', res.roi, nperm));

fig1_name = fullfile(data_dir, sprintf('LME_%s_CBPT_2D_like_dislike_FreqTime_5s_nperm%d_Fstats.png', roi_prefix, nperm));
saveas(fig1, fig1_name);
close(fig1);

fig2 = figure('Position', [150 150 1200 500], 'Visible', 'off');
subplot(1, 3, 1);
surf(TT, FF, res.avg_pref.dislike, 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, jet);
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('Dislike mean z-power');

subplot(1, 3, 2);
surf(TT, FF, res.avg_pref.like, 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, jet);
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('Like mean z-power');

subplot(1, 3, 3);
surf(TT, FF, res.diff_map, 'EdgeColor', 'none');
view(2); set_pow2_yticks(freq_vec); axis tight; colorbar; colormap(gca, redblue);
hold on;
draw_cluster_boundaries(res.h_pref, t_vec, freq_vec, max(res.diff_map(:), [], 'omitnan') + 1e-6, 'k');
xlabel('Time (ms)'); ylabel('Frequency (Hz)'); title('Like - dislike');
sgtitle(sprintf('%s condition averages, 5 s, nperm=%d', res.roi, nperm));

fig2_name = fullfile(data_dir, sprintf('LME_%s_CBPT_2D_like_dislike_FreqTime_5s_nperm%d_Averages.png', roi_prefix, nperm));
saveas(fig2, fig2_name);
close(fig2);

fprintf('Saved figures -> %s ; %s\n', fig1_name, fig2_name);
print_cluster_summary(res);
end

function draw_cluster_boundaries(h_mask, t_vec, freq_vec, z0, color_spec)
if any(h_mask(:))
    B = bwboundaries(h_mask > 0, 'noholes');
    for k = 1:numel(B)
        pix = B{k};
        f_idx = pix(:, 1);
        t_idx = pix(:, 2);
        plot3(t_vec(t_idx), freq_vec(f_idx), z0 * ones(size(f_idx)), color_spec, 'LineWidth', 2);
    end
    set(gca, 'Clipping', 'off');
end
end

function print_cluster_summary(res)
if ~isfield(res, 'clusterinfo_pref') || ~isfield(res.clusterinfo_pref, 'pos_clusters')
    return;
end
fprintf('\n== Significant clusters: %s ==\n', res.roi);
ci = res.clusterinfo_pref;
for k = 1:numel(ci.pos_clusters)
    if ci.pos_clusters(k).p < 0.05
        mask = ci.pos_clusters(k).inds;
        [fi, ti] = find(mask);
        mean_diff = mean(res.diff_map(mask), 'omitnan');
        fprintf('Cluster %d: p=%.4f, size=%d, %.2f-%.2f Hz, %.1f-%.1f ms, mean like-dislike=%.3f\n', ...
            k, ci.pos_clusters(k).p, nnz(mask), min(res.freq_vec(fi)), max(res.freq_vec(fi)), ...
            min(res.t_vec(ti)), max(res.t_vec(ti)), mean_diff);
    end
end
end

function set_pow2_yticks(freq_vec)
yl = [min(freq_vec(:)) max(freq_vec(:))];
p1 = ceil(log2(max(yl(1), eps)));
p2 = floor(log2(yl(2)));
ticks = 2 .^ (p1:p2);
ticks = ticks(ticks >= 2);
set(gca, 'YScale', 'log');
set(gca, 'YLim', yl);
set(gca, 'YTick', ticks);
set(gca, 'YTickLabel', compose('%g', ticks));
end

function cmap = redblue(m)
if nargin < 1
    m = 256;
end
if mod(m, 2) == 1
    m = m + 1;
end
r = [ones(m/2, 1); linspace(1, 0, m/2)'];
g = [linspace(0, 1, m/2)'; linspace(1, 0, m/2)'];
b = [linspace(0, 1, m/2)'; ones(m/2, 1)];
cmap = [r g b];
end

function S = load_assert(fname, fields)
assert(isfile(fname), 'File not found: %s', fname);
S = load(fname, '-mat');
for i = 1:numel(fields)
    assert(isfield(S, fields{i}), 'Missing variable %s in %s', fields{i}, fname);
end
end

function [h, p, clusterinfo] = cluster_test(datobs, datrnd, tail, alpha, clusteralpha, clusterstat)
if nargin < 3 || isempty(tail), tail = 0; end
if nargin < 4 || isempty(alpha), alpha = 0.05; end
if nargin < 5 || isempty(clusteralpha), clusteralpha = 0.05; end
if nargin < 6 || isempty(clusterstat), clusterstat = 'sum'; end

rndsiz = size(datrnd);
rnddim = numel(rndsiz);
numrnd = rndsiz(rnddim);
if ~(all(size(datobs) == rndsiz(1:end-1)) || isvector(datobs) && numel(datobs) == rndsiz(1))
    error('datobs and datrnd are not of compatible dimensionality');
end

cluster_stat_sum = strcmp(clusterstat, 'sum');
cluster_stat_size = strcmp(clusterstat, 'size');
if ~cluster_stat_sum && ~cluster_stat_size
    error('unsupported clusterstat');
end

if tail == 0
    clusteralpha = clusteralpha / 2;
end
cluster_threshold_neg = quantile(datrnd, clusteralpha, rnddim);
cluster_threshold_pos = quantile(datrnd, 1 - clusteralpha, rnddim);

[clus_observed_pos, clus_observed_neg, pos_inds, neg_inds] = find_and_characterize_clusters(datobs);
null_pos = nan(numrnd, 1);
null_neg = nan(numrnd, 1);
indvec(1:rnddim) = {':'};
for k = 1:numrnd
    if mod(k, max(1, round(numrnd / 10))) == 0
        fprintf('  cluster permutation %d/%d\n', k, numrnd);
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
    clus_p_pos(k) = (sum(null_pos > clus_observed_pos(k)) + 1) / (numrnd + 1);
end
clus_p_neg = ones(size(clus_observed_neg));
for k = 1:numel(clus_observed_neg)
    clus_p_neg(k) = (sum(null_neg < clus_observed_neg(k)) + 1) / (numrnd + 1);
end

clusterinfo = struct();
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

    function [clus_stats_pos, clus_stats_neg, pos_inds_local, neg_inds_local] = find_and_characterize_clusters(dat)
        if tail >= 0
            [clus_stats_pos, pos_inds_local] = compute_cluster_stats(dat, dat >= cluster_threshold_pos);
        else
            clus_stats_pos = [];
            pos_inds_local = [];
        end
        if tail <= 0
            [clus_stats_neg, neg_inds_local] = compute_cluster_stats(dat, dat <= cluster_threshold_neg);
        else
            clus_stats_neg = [];
            neg_inds_local = [];
        end
    end

    function [clus_stats, inds] = compute_cluster_stats(dat, clus_cand)
        connected = bwconncomp(clus_cand);
        inds = connected.PixelIdxList;
        if cluster_stat_sum
            lens = cellfun(@numel, inds);
            inds = inds(lens > 1);
            clus_stats = zeros(numel(inds), 1);
            for l = 1:numel(inds)
                clus_stats(l) = sum(dat(inds{l}));
            end
        elseif cluster_stat_size
            clus_stats = zeros(numel(inds), 1);
            for l = 1:connected.NumObjects
                clus_stats(l) = numel(connected.PixelIdxList{l});
            end
        end
    end
end
