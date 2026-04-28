from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import scipy.signal as sps
from scipy import ndimage
from scipy.stats import f as f_dist
from scipy.stats import ttest_1samp, ttest_ind
from statsmodels.formula.api import mixedlm
from statsmodels.tsa.stattools import grangercausalitytests

from .config import PipelineConfig
from .types import EpochData, TimeFrequencyResult


def _pick_region_pairs(channel_names: list[str], regions: list[str]) -> list[tuple[int, int, str]]:
    amyg = [(i, nm) for i, (nm, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "amygdala"]
    hip = [(i, nm) for i, (nm, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "hippocampus"]
    pairs = []
    for ia, na in amyg:
        for ih, nh in hip:
            pairs.append((ia, ih, f"{na}__{nh}"))
    return pairs


def compute_band_granger(ep: EpochData, regions: list[str], cfg: PipelineConfig) -> pd.DataFrame:
    pairs = _pick_region_pairs(ep.channel_names, regions)
    bands = {
        "theta": (4.0, 8.0),
        "beta": (13.0, 30.0),
    }
    rows: list[dict[str, object]] = []

    for tr in range(ep.data.shape[0]):
        for ia, ih, pair_name in pairs:
            x = ep.data[tr, ia]
            y = ep.data[tr, ih]
            for band_name, (lo, hi) in bands.items():
                sos = sps.butter(4, [lo, hi], btype="bandpass", fs=ep.sfreq, output="sos")
                xa = sps.sosfiltfilt(sos, x)
                yh = sps.sosfiltfilt(sos, y)
                dat_ah = np.column_stack([yh, xa])
                dat_ha = np.column_stack([xa, yh])
                try:
                    res_ah = grangercausalitytests(dat_ah, maxlag=10, verbose=False)
                    res_ha = grangercausalitytests(dat_ha, maxlag=10, verbose=False)
                    f_ah = max(v[0]["ssr_ftest"][0] for v in res_ah.values())
                    f_ha = max(v[0]["ssr_ftest"][0] for v in res_ha.values())
                except Exception:
                    f_ah = np.nan
                    f_ha = np.nan

                rows.append(
                    {
                        "subject": ep.subject,
                        "trial": tr,
                        "pair": pair_name,
                        "band": band_name,
                        "A_to_H_gc": f_ah,
                        "H_to_A_gc": f_ha,
                        "valence": str(ep.trial_info.iloc[tr]["valence"]),
                    }
                )

    return pd.DataFrame(rows)


def compute_band_coherence(ep: EpochData, regions: list[str], cfg: PipelineConfig) -> pd.DataFrame:
    pairs = _pick_region_pairs(ep.channel_names, regions)
    bands = {
        "theta": (4.0, 8.0),
        "beta": (13.0, 30.0),
    }
    rows: list[dict[str, object]] = []

    for tr in range(ep.data.shape[0]):
        for ia, ih, pair_name in pairs:
            x = ep.data[tr, ia]
            y = ep.data[tr, ih]
            f, cxy = sps.coherence(x, y, fs=ep.sfreq, nperseg=min(1024, len(x)))

            for band_name, (lo, hi) in bands.items():
                mask = (f >= lo) & (f <= hi)
                if np.any(mask):
                    coh_val = float(np.nanmean(cxy[mask]))
                else:
                    coh_val = np.nan

                rows.append(
                    {
                        "subject": ep.subject,
                        "trial": tr,
                        "pair": pair_name,
                        "band": band_name,
                        "A_H_coherence": coh_val,
                        "valence": str(ep.trial_info.iloc[tr]["valence"]),
                    }
                )

    return pd.DataFrame(rows)


def build_lme_dataframe(
    tf_by_subject: dict[str, TimeFrequencyResult],
    trial_info_by_subject: dict[str, pd.DataFrame],
    channel_names_by_subject: dict[str, list[str]],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    first_sub = next(iter(tf_by_subject.keys()))
    freqs = tf_by_subject[first_sub].freqs
    times = tf_by_subject[first_sub].times_ds

    for sub, tf_res in tf_by_subject.items():
        z = tf_res.z_power_ds
        trial_info = trial_info_by_subject[sub].reset_index(drop=True)
        ch_names = channel_names_by_subject[sub]
        for tr in range(z.shape[0]):
            valence = str(trial_info.iloc[tr]["valence"]).lower()
            for ch in range(z.shape[1]):
                rows.append(
                    {
                        "subject": sub,
                        "channel": ch_names[ch],
                        "subject_channel": f"{sub}:{ch_names[ch]}",
                        "valence": valence,
                        "patch": z[tr, ch],
                    }
                )

    df = pd.DataFrame(rows, columns=["subject", "channel", "subject_channel", "valence", "patch"])
    if df.empty:
        y = np.empty((0, len(freqs), len(times)), dtype=float)
        return df, y, freqs, times

    y = np.stack(df["patch"].to_list(), axis=0)
    return df, y, freqs, times


def _stack_one_sample_from_tf(tf_by_subject: dict[str, TimeFrequencyResult]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not tf_by_subject:
        empty_freqs = np.array([], dtype=float)
        empty_times = np.array([], dtype=float)
        return np.empty((0, 0, 0), dtype=float), empty_freqs, empty_times
    first_sub = next(iter(tf_by_subject.keys()))
    freqs = tf_by_subject[first_sub].freqs
    times = tf_by_subject[first_sub].times_ds
    patches = []
    for tf_res in tf_by_subject.values():
        z = tf_res.z_power_ds
        if z.size == 0:
            continue
        patches.append(z.reshape(-1, z.shape[2], z.shape[3]))
    if not patches:
        return np.empty((0, len(freqs), len(times)), dtype=float), freqs, times
    return np.concatenate(patches, axis=0), freqs, times


def run_lme_ft(df: pd.DataFrame, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if y.size == 0 or df.empty:
        return np.empty((0, 0), dtype=float), np.empty((0, 0), dtype=float)

    n_rows, n_f, n_t = y.shape
    f_map = np.full((n_f, n_t), np.nan, dtype=float)
    p_map = np.full((n_f, n_t), np.nan, dtype=float)

    base = df[["subject", "subject_channel", "valence"]].copy()

    for fi in range(n_f):
        for ti in range(n_t):
            yy = y[:, fi, ti]
            ok = np.isfinite(yy)
            if np.sum(ok) < 20:
                continue
            tbl = base.loc[ok].copy()
            tbl["data"] = yy[ok]
            tbl["valence"] = pd.Categorical(tbl["valence"], categories=["negative", "positive"])
            try:
                model = mixedlm(
                    "data ~ C(valence)",
                    data=tbl,
                    groups=tbl["subject"],
                    vc_formula={"subject_channel": "0 + C(subject_channel)"},
                )
                fit = model.fit(reml=True, method="lbfgs", disp=False)
                coef = fit.params.get("C(valence)[T.positive]", np.nan)
                se = fit.bse.get("C(valence)[T.positive]", np.nan)
                if np.isfinite(coef) and np.isfinite(se) and se > 0:
                    tval = coef / se
                    fval = tval**2
                    pval = 1.0 - f_dist.cdf(fval, 1, max(len(tbl) - 2, 1))
                    f_map[fi, ti] = fval
                    p_map[fi, ti] = pval
            except Exception:
                continue

    return f_map, p_map


def _one_sample_ft(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if y.ndim != 3:
        raise ValueError("y must be [obs, freq, time]")
    if y.shape[0] < 2:
        empty = np.empty((0, 0), dtype=float)
        return empty, empty

    n_obs, n_f, n_t = y.shape
    f_map = np.full((n_f, n_t), np.nan, dtype=float)
    p_map = np.full((n_f, n_t), np.nan, dtype=float)
    for fi in range(n_f):
        for ti in range(n_t):
            yy = y[:, fi, ti]
            ok = np.isfinite(yy)
            if np.sum(ok) < 2:
                continue
            tval, pval = ttest_1samp(yy[ok], popmean=0.0, nan_policy="omit")
            if np.isfinite(tval) and np.isfinite(pval):
                f_map[fi, ti] = float(tval) ** 2
                p_map[fi, ti] = float(pval)
    return f_map, p_map


def _one_sample_cluster_2d(y: np.ndarray, n_perm: int = 1000, seed: int = 42) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    if y.ndim != 3:
        raise ValueError("y must be [obs, freq, time]")
    if y.shape[0] < 2:
        empty = np.zeros(y.shape[1:], dtype=bool)
        return empty, np.ones(y.shape[1:], dtype=float), []

    t_obs, p_obs = ttest_1samp(y, popmean=0.0, axis=0, nan_policy="omit")
    t_obs = np.nan_to_num(t_obs, nan=0.0)
    p_obs = np.nan_to_num(p_obs, nan=1.0)
    mask = p_obs < 0.05

    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=int)
    lbl, n_lbl = ndimage.label(mask, structure=structure)

    rng = np.random.default_rng(seed)
    max_masses = np.zeros(n_perm, dtype=float)

    for pi in range(n_perm):
        signs = rng.choice([-1.0, 1.0], size=y.shape[0])[:, None, None]
        y_perm = y * signs
        t_perm, p_perm = ttest_1samp(y_perm, popmean=0.0, axis=0, nan_policy="omit")
        t_perm = np.nan_to_num(t_perm, nan=0.0)
        p_perm = np.nan_to_num(p_perm, nan=1.0)
        m_perm = p_perm < 0.05
        l_perm, n_perm_lbl = ndimage.label(m_perm, structure=structure)
        if n_perm_lbl > 0:
            max_masses[pi] = max(float(np.sum(np.abs(t_perm[l_perm == ci]))) for ci in range(1, n_perm_lbl + 1))

    h = np.zeros_like(mask, dtype=bool)
    p_cluster_map = np.ones_like(t_obs, dtype=float)
    info = []

    for ci in range(1, n_lbl + 1):
        cl = lbl == ci
        mass = float(np.sum(np.abs(t_obs[cl])))
        p_cl = (1 + np.sum(max_masses >= mass)) / (1 + n_perm)
        p_cluster_map[cl] = p_cl
        if p_cl < 0.05:
            h[cl] = True
        info.append({"cluster": float(ci), "mass": mass, "p": p_cl})

    return h, p_cluster_map, info


def cluster_permutation_2d(y: np.ndarray, labels: np.ndarray, n_perm: int = 1000, seed: int = 42) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    if y.ndim != 3:
        raise ValueError("y must be [obs, freq, time]")
    labels = np.asarray(labels).astype(str)
    g1 = labels == "negative"
    g2 = labels == "positive"

    if np.sum(g1) < 2 or np.sum(g2) < 2:
        empty = np.zeros(y.shape[1:], dtype=bool)
        return empty, np.ones(y.shape[1:], dtype=float), []

    t_obs, p_obs = ttest_ind(y[g2], y[g1], axis=0, equal_var=False, nan_policy="omit")
    t_obs = np.nan_to_num(t_obs, nan=0.0)
    p_obs = np.nan_to_num(p_obs, nan=1.0)
    mask = p_obs < 0.05

    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=int)
    lbl, n_lbl = ndimage.label(mask, structure=structure)

    masses = []
    for ci in range(1, n_lbl + 1):
        cl = lbl == ci
        masses.append(float(np.sum(np.abs(t_obs[cl]))))

    rng = np.random.default_rng(seed)
    max_masses = np.zeros(n_perm, dtype=float)

    for pi in range(n_perm):
        perm = labels.copy()
        rng.shuffle(perm)
        p1 = perm == "negative"
        p2 = perm == "positive"
        if np.sum(p1) < 2 or np.sum(p2) < 2:
            continue
        t_perm, p_perm = ttest_ind(y[p2], y[p1], axis=0, equal_var=False, nan_policy="omit")
        t_perm = np.nan_to_num(t_perm, nan=0.0)
        p_perm = np.nan_to_num(p_perm, nan=1.0)
        m_perm = p_perm < 0.05
        l_perm, n_perm_lbl = ndimage.label(m_perm, structure=structure)
        if n_perm_lbl > 0:
            max_masses[pi] = max(float(np.sum(np.abs(t_perm[l_perm == ci]))) for ci in range(1, n_perm_lbl + 1))

    h = np.zeros_like(mask, dtype=bool)
    p_cluster_map = np.ones_like(t_obs, dtype=float)
    info = []

    for ci in range(1, n_lbl + 1):
        cl = lbl == ci
        mass = float(np.sum(np.abs(t_obs[cl])))
        p_cl = (1 + np.sum(max_masses >= mass)) / (1 + n_perm)
        p_cluster_map[cl] = p_cl
        if p_cl < 0.05:
            h[cl] = True
        info.append({"cluster": float(ci), "mass": mass, "p": p_cl})

    return h, p_cluster_map, info


def run_lme_and_cbpt(
    tf_by_subject: dict[str, TimeFrequencyResult],
    trial_info_by_subject: dict[str, pd.DataFrame],
    channel_names_by_subject: dict[str, list[str]],
    cfg: PipelineConfig,
) -> dict[str, object]:
    if not tf_by_subject:
        empty_map = np.empty((0, 0), dtype=float)
        return {
            "freqs": np.array([], dtype=float),
            "times": np.array([], dtype=float),
            "analysis_mode": "empty",
            "F_val": empty_map,
            "P_val": empty_map,
            "h_val": np.zeros((0, 0), dtype=bool),
            "P_val_clust": empty_map,
            "clusterinfo_val": [],
        }

    can_build_contrast = bool(trial_info_by_subject) and bool(channel_names_by_subject) and all(
        sub in trial_info_by_subject and sub in channel_names_by_subject for sub in tf_by_subject
    )
    if not can_build_contrast:
        y, freqs, times = _stack_one_sample_from_tf(tf_by_subject)
        f_map, p_map = _one_sample_ft(y)
        h_map, p_cluster, cluster_info = _one_sample_cluster_2d(
            y=np.nan_to_num(y),
            n_perm=cfg.n_permutations,
            seed=cfg.random_seed,
        )
        return {
            "freqs": freqs,
            "times": times,
            "analysis_mode": "one_sample",
            "F_val": f_map,
            "P_val": p_map,
            "h_val": h_map,
            "P_val_clust": p_cluster,
            "clusterinfo_val": cluster_info,
        }

    df, y, freqs, times = build_lme_dataframe(tf_by_subject, trial_info_by_subject, channel_names_by_subject)
    labels = df["valence"].astype(str).to_numpy()

    unique_labels = {lab for lab in np.unique(labels.astype(str)) if lab and lab != "nan"}
    if df.empty or y.size == 0:
        y, freqs, times = _stack_one_sample_from_tf(tf_by_subject)
        empty_map = np.empty((0, 0), dtype=float) if y.size == 0 else np.full(y.shape[1:], np.nan, dtype=float)
        return {
            "freqs": freqs,
            "times": times,
            "analysis_mode": "empty",
            "F_val": empty_map,
            "P_val": empty_map,
            "h_val": np.zeros((0, 0), dtype=bool),
            "P_val_clust": empty_map,
            "clusterinfo_val": [],
        }

    if {"negative", "positive"}.issubset(unique_labels):
        contrast_mask = np.isin(labels, ["negative", "positive"])
        df_contrast = df.loc[contrast_mask].reset_index(drop=True)
        y_contrast = y[contrast_mask]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f_map, p_map = run_lme_ft(df_contrast, y_contrast)

        h_map, p_cluster, cluster_info = cluster_permutation_2d(
            y=np.nan_to_num(y_contrast),
            labels=labels[contrast_mask],
            n_perm=cfg.n_permutations,
            seed=cfg.random_seed,
        )
        analysis_mode = "valence_contrast"
    else:
        y, freqs, times = _stack_one_sample_from_tf(tf_by_subject)
        f_map, p_map = _one_sample_ft(y)
        h_map, p_cluster, cluster_info = _one_sample_cluster_2d(
            y=np.nan_to_num(y),
            n_perm=cfg.n_permutations,
            seed=cfg.random_seed,
        )
        analysis_mode = "one_sample"

    return {
        "freqs": freqs,
        "times": times,
        "analysis_mode": analysis_mode,
        "F_val": f_map,
        "P_val": p_map,
        "h_val": h_map,
        "P_val_clust": p_cluster,
        "clusterinfo_val": cluster_info,
    }
