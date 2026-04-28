from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.signal as sps
from mne.time_frequency import tfr_array_morlet

from .config import PipelineConfig
from .types import EpochData, TimeFrequencyResult


def compute_tf_bootstrap_z(ep: EpochData, cfg: PipelineConfig) -> TimeFrequencyResult:
    x = ep.data.astype(np.float32)
    freqs = cfg.tf_freqs
    n_cycles = cfg.tf_n_cycles

    power = tfr_array_morlet(
        x,
        sfreq=ep.sfreq,
        freqs=freqs,
        n_cycles=n_cycles,
        output="power",
        zero_mean=True,
        n_jobs=1,
    )

    t = ep.times
    base_idx = np.where((t >= cfg.baseline_tmin) & (t <= cfg.baseline_tmax))[0]
    if base_idx.size == 0:
        raise ValueError("No baseline samples in epoch window")

    n_trials, n_ch, n_freq, n_time = power.shape
    z_power = np.zeros_like(power, dtype=np.float32)
    rng = np.random.default_rng(cfg.random_seed)

    for ch in range(n_ch):
        for fi in range(n_freq):
            base_vals = power[:, ch, fi, :][:, base_idx].reshape(-1)
            if base_vals.size == 0:
                continue
            boot_means = np.empty(cfg.tf_bootstrap_n, dtype=np.float64)
            for bi in range(cfg.tf_bootstrap_n):
                sample = rng.choice(base_vals, size=n_trials, replace=True)
                boot_means[bi] = np.mean(sample)
            mu = np.mean(boot_means)
            sigma = max(np.std(boot_means), 1e-12)
            z_power[:, ch, fi, :] = (power[:, ch, fi, :] - mu) / sigma

    bin_size = max(1, int(round(cfg.tf_bin_ms / 1000.0 * ep.sfreq)))
    idx = np.arange(0, n_time, bin_size)
    z_ds = z_power[:, :, :, idx]
    times_ds = t[idx]

    labels = ep.trial_info["valence"].astype(str).str.lower().to_numpy()
    cond_mean = {}
    present_labels = [lab for lab in sorted(pd.unique(labels)) if lab and lab != "nan"]
    if not present_labels:
        present_labels = ["all"]
    for cond in present_labels:
        mask = labels == cond if cond != "all" else np.ones_like(labels, dtype=bool)
        if np.any(mask):
            cond_mean[cond] = np.mean(z_ds[mask], axis=0)
        else:
            cond_mean[cond] = np.full((n_ch, n_freq, len(idx)), np.nan, dtype=np.float32)

    return TimeFrequencyResult(
        z_power_ds=z_ds,
        freqs=freqs,
        times_ds=times_ds,
        cond_mean_z=cond_mean,
    )


def high_gamma_envelope(ep: EpochData, cfg: PipelineConfig) -> np.ndarray:
    sos = sps.butter(4, [cfg.hgamma_low, cfg.hgamma_high], btype="bandpass", fs=ep.sfreq, output="sos")
    hg = sps.sosfiltfilt(sos, ep.data, axis=2)
    analytic = sps.hilbert(hg, axis=2)
    return np.abs(analytic)
