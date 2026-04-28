from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat
from pynwb import NWBHDF5IO

from .config import PipelineConfig
from .connectivity_stats import compute_band_granger, run_lme_and_cbpt
from .export import save_group_mat, save_subject_mat
from .nwb_io import (
    _infer_subject_id,
    iter_nwb_files,
    load_events,
    load_subject_lfp_from_nwb,
)
from .preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from .spikes import ifr_hgamma_coupling
from .time_frequency import compute_tf_bootstrap_z


def _load_cached_tf_result(mat_path: Path):
    mat = loadmat(str(mat_path), squeeze_me=True, struct_as_record=False)
    z_power_ds = np.asarray(mat["z_power_ds"], dtype=np.float32)
    freqs = np.asarray(mat["freqs"], dtype=np.float32).ravel()
    tms_ds = np.asarray(mat["tms_ds"], dtype=np.float32).ravel() / 1000.0
    from .types import TimeFrequencyResult

    return TimeFrequencyResult(z_power_ds=z_power_ds, freqs=freqs, times_ds=tms_ds, cond_mean_z={})


def _load_units_table(nwb_path: Path) -> pd.DataFrame:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            return pd.DataFrame({"spike_times": []})
        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            return pd.DataFrame({"spike_times": []})
        return units[["spike_times"]].copy()


def run_pipeline(cfg: PipelineConfig) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(cfg.event_csv)
    nwb_files = iter_nwb_files(cfg.data_dir)
    if not nwb_files:
        raise ValueError(f"No .nwb files found in {cfg.data_dir}")

    tf_by_subject = {}
    trial_info_by_subject = {}
    channel_names_by_subject = {}

    for nwb_path in nwb_files:
        subject_id = _infer_subject_id(nwb_path)
        out_file = cfg.output_dir / f"{subject_id}_scene_python_results.mat"
        if out_file.exists():
            print(f"Skipping {subject_id} as {out_file.name} already exists.")
            try:
                tf_by_subject[subject_id] = _load_cached_tf_result(out_file)
            except Exception as exc:
                print(f"Warning: could not load cached TF result for {subject_id}: {exc}")
            continue

        sig = load_subject_lfp_from_nwb(nwb_path)
        sig_pp = preprocess_signal(sig, cfg)
        ep = epoch_subject(sig_pp, events, cfg)
        ep_clean, qc = run_hybrid_qc(ep, cfg)

        tf_res = compute_tf_bootstrap_z(ep_clean, cfg)
        units_df = _load_units_table(nwb_path)
        spike_res = ifr_hgamma_coupling(units_df, ep_clean, cfg)
        sgc_df = compute_band_granger(ep_clean, sig_pp.region, cfg)

        save_subject_mat(cfg.output_dir, sig.subject, tf_res, qc, spike_res, sgc_df)

        tf_by_subject[sig.subject] = tf_res
        trial_info_by_subject[sig.subject] = ep_clean.trial_info.copy()
        channel_names_by_subject[sig.subject] = ep_clean.channel_names

    group_stats = run_lme_and_cbpt(tf_by_subject, trial_info_by_subject, channel_names_by_subject, cfg)
    save_group_mat(cfg.output_dir, group_stats)
