from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import savemat

from .types import SpikeResult, TimeFrequencyResult


def _to_records_with_columns(df: pd.DataFrame, expected_cols: list[str]) -> np.recarray:
    """Return a structured array even when df is empty or has missing columns."""
    if df is None:
        df = pd.DataFrame(columns=expected_cols)
    else:
        df = df.copy()
        for col in expected_cols:
            if col not in df.columns:
                df[col] = np.nan
        df = df[expected_cols]
    return df.to_records(index=False)


def save_subject_mat(
    out_dir: Path,
    subject: str,
    tf_res: TimeFrequencyResult,
    qc: dict[str, np.ndarray],
    spike_res: SpikeResult,
    sgc_df,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{subject}_scene_python_results.mat"

    coupling_rec = _to_records_with_columns(
        spike_res.coupling,
        ["subject", "trial", "valence", "spearman_rho", "p_value"],
    )
    sgc_rec = _to_records_with_columns(
        sgc_df,
        ["subject", "trial", "pair", "band", "A_to_H_gc", "H_to_A_gc", "valence"],
    )

    savemat(
        out_file,
        {
            "z_power_ds": tf_res.z_power_ds.astype(np.float32),
            "freqs": tf_res.freqs.astype(np.float32),
            "tms_ds": tf_res.times_ds.astype(np.float32) * 1000.0,
            "QC": {
                "keep_idx": qc["keep_idx"] + 1,
                "reject_idx": qc["reject_idx"] + 1,
                "reject_mask": qc["reject_mask"],
                "flag_rms": qc["flag_rms"],
                "flag_p2p": qc["flag_p2p"],
                "flag_abs": qc["flag_abs"],
                "flag_p2p3s": qc["flag_p2p3s"],
            },
            "IFR": spike_res.ifr,
            "IFR_times": spike_res.ifr_times,
            "PSTH_negative": spike_res.psth["negative"],
            "PSTH_neutral": spike_res.psth["neutral"],
            "PSTH_positive": spike_res.psth["positive"],
            "IFR_HG_coupling": coupling_rec,
            "sGC_table": sgc_rec,
        },
        do_compression=True,
    )


def save_group_mat(out_dir: Path, group_stats: dict[str, object]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "group_LME_CBPT_valence_python.mat"
    savemat(out_file, {"res": group_stats}, do_compression=True)
