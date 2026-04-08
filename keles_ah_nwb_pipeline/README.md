# Keles 2024 A-H NWB Python Pipeline

Python rewrite of the MATLAB sEEG/spike workflow for Amygdala-Hippocampus interactions during movie watching.

## Implemented modules

1. **Data loading & preprocessing**
   - Load `.nwb` by `pynwb` with lazy-accessed datasets.
   - Select channels localized to Amygdala/Hippocampus from electrode labels/locations.
   - Bipolar reference from adjacent contacts.
   - Resample to `1000 Hz`, bandpass `1-200 Hz`, notch `50 Hz`.
   - Epoch window `[-0.5, 2.0] s` from `event_csv` tags.
   - Hybrid QC:
     - Robust MAD-Z reject if `$Z>4$` for RMS log-ratio / post-window P2P.
     - Hard reject if `abs >= 200 uV`.

2. **Time-frequency analysis**
   - Morlet TF (`mne.time_frequency.tfr_array_morlet`).
   - `2-120 Hz` (24 log-spaced frequencies), cycles `3-12` (log-spaced).
   - Bootstrap baseline z-score over `[-0.5, 0] s` with `n=1000`.
   - Downsample to `50 ms` bins.

3. **Spike & multi-scale**
   - Use `nwb.units.spike_times`.
   - IFR via Elephant Gaussian kernel (`50 ms`).
   - PSTH per valence.
   - Spearman coupling between IFR and high-gamma (`70-150 Hz`) envelope.

4. **Connectivity & statistics**
   - Trial-wise A↔H Granger F-tests in theta/beta bands.
   - Group LME (statsmodels approximation): `data ~ C(valence) + (1|subject) + (1|subject:channel)`.
   - 2D cluster permutation test across freq-time map.

5. **MATLAB compatibility export**
   - Subject outputs: `subXXX_scene_python_results.mat`
   - Group output: `group_LME_CBPT_valence_python.mat`

## Files

- `run_pipeline.py`: CLI entry point
- `ah_pipeline/nwb_io.py`: NWB loading, channel selection, bipolar pairing
- `ah_pipeline/preprocessing.py`: filtering, epoching, hybrid QC
- `ah_pipeline/time_frequency.py`: Morlet TF + bootstrap z + HG envelope
- `ah_pipeline/spikes.py`: IFR, PSTH, spike-LFP coupling
- `ah_pipeline/connectivity_stats.py`: sGC, LME, CBPT
- `ah_pipeline/export.py`: `.mat` export

## Install

```bash
cd /Volumes/人盘含鱼纹/keles_ah_nwb_pipeline
python -m pip install -r requirements.txt
```

## Run

```bash
python run_pipeline.py \
  --data-dir /path/to/nwb_dir \
  --event-csv /path/to/events.csv \
  --output-dir /Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/results \
  --n-perm 1000
```

## Event CSV format

Required columns:

- `subject`: e.g., `sub001`
- `onset`: event onset in seconds (same timeline as NWB LFP)
- `valence`: `negative | neutral | positive`
- `event_type`: `event_boundary | valence_tag | ...` (kept for traceability)

Use `events_template.csv` as template.

## Notes

- If your NWB stores A/H labels in different columns, update region parsing in `nwb_io.py`.
- For full frequency-domain Granger implementation, `mne-connectivity` can be added as backend.
- `pymer4` is optional; current default LME backend uses `statsmodels`.
