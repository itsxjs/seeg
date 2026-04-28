from __future__ import annotations

import numpy as np
import pandas as pd
import quantities as pq
from elephant.kernels import GaussianKernel
from elephant.statistics import instantaneous_rate
from neo import SpikeTrain
from scipy.stats import spearmanr

from .config import PipelineConfig
from .types import EpochData, SpikeResult
from .time_frequency import high_gamma_envelope


def compute_ifr_and_psth(units_df: pd.DataFrame, ep: EpochData, cfg: PipelineConfig) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    t_start = float(ep.times[0])
    t_stop = float(ep.times[-1])
    bin_s = cfg.ifr_bin_ms / 1000.0
    n_bins = int(np.floor((t_stop - t_start) / bin_s)) + 1
    ifr_time = t_start + np.arange(n_bins) * bin_s

    kernel = GaussianKernel(sigma=(cfg.ifr_gauss_ms / 1000.0) * pq.s)
    ifr_trials = np.zeros((len(ep.trial_info), n_bins), dtype=np.float32)

    for tr_idx, row in ep.trial_info.reset_index(drop=True).iterrows():
        onset = float(row["onset"])
        trial_rates = []
        for st_arr in units_df["spike_times"].to_list():
            rel = np.asarray(st_arr, dtype=float) - onset
            rel = rel[(rel >= t_start) & (rel <= t_stop)]
            if rel.size == 0:
                continue
            spk = SpikeTrain(rel * pq.s, t_start=t_start * pq.s, t_stop=t_stop * pq.s)
            rate = instantaneous_rate(spk, sampling_period=bin_s * pq.s, kernel=kernel)
            trial_rates.append(np.asarray(rate).squeeze())
        if trial_rates:
            min_len = min(len(r) for r in trial_rates)
            ifr_trials[tr_idx, :min_len] = np.mean(np.stack([r[:min_len] for r in trial_rates], axis=0), axis=0)

    labels = ep.trial_info["valence"].astype(str).str.lower().to_numpy()
    psth = {
        "negative": np.nanmean(ifr_trials[labels == "negative"], axis=0) if np.any(labels == "negative") else np.full(n_bins, np.nan),
        "neutral": np.nanmean(ifr_trials[labels == "neutral"], axis=0) if np.any(labels == "neutral") else np.full(n_bins, np.nan),
        "positive": np.nanmean(ifr_trials[labels == "positive"], axis=0) if np.any(labels == "positive") else np.full(n_bins, np.nan),
    }
    return ifr_trials, ifr_time, psth


def ifr_hgamma_coupling(units_df: pd.DataFrame, ep: EpochData, cfg: PipelineConfig) -> SpikeResult:
    ifr_trials, ifr_time, psth = compute_ifr_and_psth(units_df, ep, cfg)
    hg = high_gamma_envelope(ep, cfg)
    hg_mean = np.mean(hg, axis=1)

    t_src = ep.times
    hg_rs = np.zeros((hg_mean.shape[0], len(ifr_time)), dtype=np.float32)
    for i in range(hg_mean.shape[0]):
        hg_rs[i] = np.interp(ifr_time, t_src, hg_mean[i])

    rows = []
    for tr in range(len(ep.trial_info)):
        rho, p = spearmanr(ifr_trials[tr], hg_rs[tr], nan_policy="omit")
        rows.append(
            {
                "subject": ep.subject,
                "trial": tr,
                "valence": str(ep.trial_info.iloc[tr]["valence"]),
                "spearman_rho": float(rho) if np.isfinite(rho) else np.nan,
                "p_value": float(p) if np.isfinite(p) else np.nan,
            }
        )

    coupling_cols = ["subject", "trial", "valence", "spearman_rho", "p_value"]
    return SpikeResult(ifr=ifr_trials, ifr_times=ifr_time, psth=psth, coupling=pd.DataFrame(rows, columns=coupling_cols))
