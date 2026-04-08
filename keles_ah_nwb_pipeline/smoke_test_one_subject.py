from pathlib import Path

from ah_pipeline.config import PipelineConfig
from ah_pipeline.nwb_io import load_subject_lfp_from_nwb, load_events
from ah_pipeline.preprocessing import preprocess_signal, epoch_subject, run_hybrid_qc

nwb = Path('/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/raw/000623/sub-CS42/sub-CS42_ses-P42CSR2_behavior+ecephys.nwb')
cfg = PipelineConfig(
    data_dir=Path('/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/raw/000623'),
    event_csv=Path('/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/smoke_events_subcs42.csv'),
    output_dir=Path('/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/results'),
)

sig = load_subject_lfp_from_nwb(nwb)
print('subject', sig.subject, 'channels', len(sig.channel_names), 'sfreq', sig.sfreq)
ev = load_events(cfg.event_csv)
ep = epoch_subject(preprocess_signal(sig, cfg), ev, cfg)
print('epoch_shape', ep.data.shape, 'n_trials', len(ep.trial_info))
clean_ep, qc = run_hybrid_qc(ep, cfg)
print('clean_shape', clean_ep.data.shape, 'kept', len(qc['keep_idx']), 'rejected', len(qc['reject_idx']))
