function run_study2_5s_smoke_test()
%% Minimal local smoke test for run_study2_5s_hcp.
% This creates tiny synthetic EEGLAB .set/.fdt files and verifies that the
% complete path runs: 2-s QC whitelist -> 5-s epoch -> TF -> LME/CBPT -> files.

this_dir = fileparts(mfilename('fullpath'));
smoke_dir = fullfile(this_dir, 'smoke_test_data');
if ~isfolder(smoke_dir)
    mkdir(smoke_dir);
end

eeglab_candidates = { ...
    '/Users/defanive/Library/eeglab2023.1', ...
    '/Users/defanive/Library/Application Support/MathWorks/MATLAB Add-Ons/Collections/EEGLAB' ...
};
eeglab_dir = '';
for k = 1:numel(eeglab_candidates)
    if isfolder(eeglab_candidates{k})
        eeglab_dir = eeglab_candidates{k};
        break;
    end
end
assert(~isempty(eeglab_dir), 'Local EEGLAB folder not found.');
addpath(genpath(eeglab_dir));
eeglab nogui;

subs = {'sub001', 'sub004', 'sub005', 'sub007', 'sub008', 'sub009'};
for isub = 1:numel(subs)
    create_synthetic_subject(smoke_dir, subs{isub}, isub);
end

cfg = struct();
cfg.project_dir = this_dir;
cfg.data_dir = smoke_dir;
cfg.eeglab_dir = eeglab_dir;
cfg.subs = subs;
cfg.nperm = 2;
cfg.n_workers = 2;
cfg.rng_seed = 123;
cfg.freqs = [6 12];
cfg.tf_bootstrap_n = 5;
cfg.ds_ms = 1000;

run_study2_5s_hcp(cfg);

expected = { ...
    'sub001_valence_BOSC_TF_zpower_5s.mat', ...
    'LME_Amydgala_CBPT_2D_like_dislike_FreqTime_5s_nperm2.mat', ...
    'LME_Hippocampus_CBPT_2D_like_dislike_FreqTime_5s_nperm2.mat' ...
};
for k = 1:numel(expected)
    assert(isfile(fullfile(smoke_dir, expected{k})), 'Missing expected smoke output: %s', expected{k});
end

fprintf('\nSMOKE TEST PASSED. Outputs are in: %s\n', smoke_dir);
end

function create_synthetic_subject(out_dir, sid, seed_offset)
rng(1000 + seed_offset);
srate = 100;
duration_s = 45;
n_pnts = duration_s * srate;
t = (0:n_pnts-1) / srate;

chan_labels = channels_for_subject(sid);
n_ch = numel(chan_labels);
data = 0.05 * randn(n_ch, n_pnts);
for ch = 1:n_ch
    data(ch, :) = data(ch, :) + 0.1 * sin(2 * pi * (4 + ch) * t);
end

ratings = [1 4 2 5 1 4 2 5];
event_sec = 3:5:38;
for ev = 1:numel(event_sec)
    idx = round(event_sec(ev) * srate);
    idx2 = min(n_pnts, idx + 5 * srate);
    if ratings(ev) >= 4
        data(:, idx:idx2) = data(:, idx:idx2) + 0.2 * sin(2 * pi * 12 * t(idx:idx2));
    else
        data(:, idx:idx2) = data(:, idx:idx2) + 0.15 * sin(2 * pi * 6 * t(idx:idx2));
    end
end

EEG = eeg_emptyset;
EEG.data = data;
EEG.nbchan = n_ch;
EEG.pnts = n_pnts;
EEG.trials = 1;
EEG.srate = srate;
EEG.xmin = 0;
EEG.xmax = (n_pnts - 1) / srate;
EEG.setname = [sid '_synthetic_rate_preproc'];
EEG.chanlocs = struct('labels', chan_labels);

for ev = 1:numel(event_sec)
    EEG.event(ev).type = num2str(ratings(ev)); %#ok<AGROW>
    EEG.event(ev).latency = event_sec(ev) * srate + 1; %#ok<AGROW>
    EEG.event(ev).urevent = ev; %#ok<AGROW>
    EEG.urevent(ev).type = EEG.event(ev).type; %#ok<AGROW>
    EEG.urevent(ev).latency = EEG.event(ev).latency; %#ok<AGROW>
end
EEG = eeg_checkset(EEG, 'eventconsistency');
pop_saveset(EEG, 'filename', [sid '_rate_preproc.set'], 'filepath', out_dir);

EEG_clean_src = EEG;
EEG_clean_src = append_clean_events_for_smoke(EEG_clean_src);
EEG_clean = pop_epoch(EEG_clean_src, {'dislike', 'like'}, [-0.5 2]);
EEG_clean = eeg_checkset(EEG_clean);
pop_saveset(EEG_clean, 'filename', [sid '_4bin_epoch_clean.set'], 'filepath', out_dir);
end

function EEG = append_clean_events_for_smoke(EEG)
new_events = EEG.event;
for i = 1:numel(EEG.event)
    rating = string(EEG.event(i).type);
    if rating == "1" || rating == "2"
        lab = 'dislike';
    elseif rating == "4" || rating == "5"
        lab = 'like';
    else
        continue;
    end
    e2 = EEG.event(i);
    e2.type = lab;
    new_events(end + 1) = e2; %#ok<AGROW>
end
EEG.event = new_events;
[~, ord] = sort([EEG.event.latency]);
EEG.event = EEG.event(ord);
EEG = eeg_checkset(EEG, 'eventconsistency');
end

function chan_labels = channels_for_subject(sid)
switch sid
    case 'sub001'
        chan_labels = {'A2-Ref', 'A1-Ref'};
    case 'sub004'
        chan_labels = {'A1-Ref', 'POL B1'};
    case 'sub005'
        chan_labels = {'A2-Ref', 'POL B1'};
    case 'sub007'
        chan_labels = {'A1-Ref', 'POL B3'};
    case 'sub008'
        chan_labels = {'A2-Ref', 'POL B1'};
    case 'sub009'
        chan_labels = {'A1-Ref', 'POL B1'};
    otherwise
        chan_labels = {'A1-Ref', 'POL B1'};
end
end
