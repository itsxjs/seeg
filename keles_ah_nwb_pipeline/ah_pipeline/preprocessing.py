from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.signal as sps

from .config import PipelineConfig
from .types import EpochData, SubjectSignals


def preprocess_signal(sig: SubjectSignals, cfg: PipelineConfig) -> SubjectSignals:
    data = sig.data
    if not np.isclose(sig.sfreq, cfg.target_sfreq):
        up = int(cfg.target_sfreq)
        down = int(sig.sfreq)
        g = np.gcd(up, down)
        data = sps.resample_poly(data, up // g, down // g, axis=1)
        sfreq = cfg.target_sfreq
    else:
        sfreq = sig.sfreq

    sos = sps.butter(4, [cfg.l_freq, cfg.h_freq], btype="bandpass", fs=sfreq, output="sos")
    data = sps.sosfiltfilt(sos, data, axis=1)

    b_notch, a_notch = sps.iirnotch(cfg.notch_freq, Q=30, fs=sfreq)
    data = sps.filtfilt(b_notch, a_notch, data, axis=1)

    return SubjectSignals(
        subject=sig.subject,
        sfreq=sfreq,
        data=data.astype(np.float32),
        channel_names=sig.channel_names,
        region=sig.region,
    )


def epoch_subject(sig: SubjectSignals, events_df: pd.DataFrame, cfg: PipelineConfig) -> EpochData:
    sub_ev = events_df.loc[events_df["subject"] == sig.subject].copy()
    if sub_ev.empty:
        raise ValueError(f"No events for subject {sig.subject}")

    n_pre = int(round(abs(cfg.epoch_tmin) * sig.sfreq))
    n_post = int(round(cfg.epoch_tmax * sig.sfreq))
    n_samp = n_pre + n_post

    trials = []
    rows = []
    for _, row in sub_ev.iterrows():
        onset = int(round(float(row["onset"]) * sig.sfreq))
        start = onset - n_pre
        stop = onset + n_post
        if start < 0 or stop > sig.data.shape[1]:
            continue
        trials.append(sig.data[:, start:stop])
        rows.append(row)

    if not trials:
        raise ValueError(f"No valid epochs for subject {sig.subject}")

    epoch_data = np.stack(trials, axis=0)
    trial_info = pd.DataFrame(rows).reset_index(drop=True)
    times = np.arange(n_samp, dtype=float) / sig.sfreq + cfg.epoch_tmin

    return EpochData(
        subject=sig.subject,
        sfreq=sig.sfreq,
        times=times,
        data=epoch_data,
        channel_names=sig.channel_names,
        trial_info=trial_info,
    )


def run_hybrid_qc(ep: EpochData, cfg: PipelineConfig) -> tuple[EpochData, dict[str, np.ndarray]]:
    data_uV = ep.data * 1e6
    t = ep.times

    base_idx = np.where((t >= cfg.baseline_tmin) & (t <= cfg.baseline_tmax))[0]
    post_idx = np.where((t >= cfg.analysis_tmin) & (t <= 1.0))[0]
    if base_idx.size == 0 or post_idx.size == 0:
        raise ValueError("Invalid baseline/post windows in QC")

    n_trials, n_ch, _ = data_uV.shape
    labels = ep.trial_info["valence"].astype(str).str.lower().to_numpy()
    present_labels = [lab for lab in sorted(pd.unique(labels)) if lab and lab != "nan"]
    if not present_labels:
        present_labels = ["all"]
    cond_masks = {lab: labels == lab for lab in present_labels}

    flag_rms = np.zeros((n_trials, n_ch), dtype=bool)
    flag_p2p = np.zeros((n_trials, n_ch), dtype=bool)

    def robust_z(vec: np.ndarray) -> np.ndarray:
        med = np.nanmedian(vec)
        mad = np.nanmedian(np.abs(vec - med))
        mad = max(mad, 1e-12)
        return 0.6745 * (vec - med) / mad

    for ch in range(n_ch):
        x = data_uV[:, ch, :]
        xb = np.sqrt(np.mean(np.square(x[:, base_idx]), axis=1))
        xp = np.sqrt(np.mean(np.square(x[:, post_idx]), axis=1))
        r = np.log(xp / np.maximum(xb, 1e-12))
        p2p_post = np.max(x[:, post_idx], axis=1) - np.min(x[:, post_idx], axis=1)

        for mask in cond_masks.values():
            idx = np.where(mask)[0]
            if idx.size == 0:
                continue
            z_r = robust_z(r[idx])
            z_p = robust_z(p2p_post[idx])
            flag_rms[idx, ch] = z_r > cfg.qc_thr_z
            flag_p2p[idx, ch] = z_p > cfg.qc_thr_z

    flag_robust = flag_rms | flag_p2p

    flag_abs = np.any(np.abs(data_uV) >= cfg.qc_abs_uV, axis=2)
    flag_p2p3s = np.zeros((n_trials, n_ch), dtype=bool)
    for ch in range(n_ch):
        p2p_full = np.max(data_uV[:, ch, :], axis=1) - np.min(data_uV[:, ch, :], axis=1)
        for key in present_labels:
            idx = np.where(cond_masks[key])[0]
            if idx.size == 0:
                continue
            mu = np.mean(p2p_full[idx])
            sd = max(np.std(p2p_full[idx]), 1e-12)
            thr = mu + cfg.qc_sigma_p2p * sd
            flag_p2p3s[idx, ch] = p2p_full[idx] > thr

    flag_sigma = flag_abs | flag_p2p3s

    reject_robust = np.sum(flag_robust, axis=1) >= cfg.qc_vote_robust
    reject_sigma = np.sum(flag_sigma, axis=1) >= cfg.qc_vote_sigma
    reject_mask = reject_robust | reject_sigma
    keep_mask = ~reject_mask

    ep_clean = EpochData(
        subject=ep.subject,
        sfreq=ep.sfreq,
        times=ep.times,
        data=ep.data[keep_mask],
        channel_names=ep.channel_names,
        trial_info=ep.trial_info.loc[keep_mask].reset_index(drop=True),
    )

    qc = {
        "keep_idx": np.where(keep_mask)[0],
        "reject_idx": np.where(reject_mask)[0],
        "reject_mask": reject_mask,
        "flag_rms": flag_rms,
        "flag_p2p": flag_p2p,
        "flag_abs": flag_abs,
        "flag_p2p3s": flag_p2p3s,
    }
    return ep_clean, qc
