from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter1d
from scipy.stats import mannwhitneyu, ttest_ind, wilcoxon

from ah_pipeline.nwb_io import iter_nwb_files, load_events


FONT_PATHS = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
]


def font(size: float) -> font_manager.FontProperties:
    for path in FONT_PATHS:
        if path.exists():
            return font_manager.FontProperties(fname=str(path), size=size)
    return font_manager.FontProperties(size=size)


def infer_subject_id(nwb_path: Path) -> str:
    m_bids = re.search(r"(sub-[A-Za-z0-9]+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_bids:
        return m_bids.group(1).lower()
    m_num = re.search(r"(sub\d+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_num:
        return m_num.group(1).lower()
    return nwb_path.stem.lower()


def region_from_text(text: str) -> str:
    t = str(text).lower()
    if "amyg" in t:
        return "杏仁核"
    if "hipp" in t or "hippocampus" in t or "hc" in t:
        return "海马"
    return "其他"


def unit_region(units: pd.DataFrame, unit_index: int) -> str:
    elec = units.iloc[unit_index].get("electrodes")
    if not hasattr(elec, "get"):
        return "未知"
    locs = elec.get("location", pd.Series([], dtype=str)).astype(str).tolist()
    labels = elec.get("label", pd.Series([], dtype=str)).astype(str).tolist()
    tags = {region_from_text(x) for x in locs + labels}
    if "杏仁核" in tags:
        return "杏仁核"
    if "海马" in tags:
        return "海马"
    return "其他"


def unit_trial_rate_matrix(
    spike_times: np.ndarray,
    onsets: np.ndarray,
    bin_edges: np.ndarray,
    tmin: float,
    tmax: float,
    smooth_sigma_bins: float,
) -> np.ndarray:
    n_trials = len(onsets)
    n_bins = len(bin_edges) - 1
    bin_s = float(bin_edges[1] - bin_edges[0])
    mat = np.zeros((n_trials, n_bins), dtype=float)

    for i, onset in enumerate(onsets):
        rel = spike_times - onset
        rel = rel[(rel >= tmin) & (rel < tmax)]
        if rel.size == 0:
            continue
        cnt, _ = np.histogram(rel, bins=bin_edges)
        mat[i] = cnt.astype(float) / max(bin_s, 1e-12)

    if smooth_sigma_bins > 0:
        mat = gaussian_filter1d(mat, sigma=smooth_sigma_bins, axis=1, mode="nearest")

    return mat


def zscore_by_baseline(curve: np.ndarray, base_idx: np.ndarray) -> np.ndarray:
    base = curve[base_idx]
    mu = float(np.mean(base))
    sd = float(np.std(base))
    if not np.isfinite(sd) or sd < 1e-8:
        return curve - mu
    return (curve - mu) / sd


def sem(curves: np.ndarray) -> np.ndarray:
    if curves.shape[0] <= 1:
        return np.zeros(curves.shape[1])
    return np.std(curves, axis=0, ddof=1) / np.sqrt(curves.shape[0])


def fdr_bh(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    pvals = np.asarray(pvals, dtype=float)
    valid = np.isfinite(pvals)
    sig = np.zeros(pvals.shape, dtype=bool)
    if not np.any(valid):
        return sig
    pv = pvals[valid]
    order = np.argsort(pv)
    ranked = pv[order]
    thresh = alpha * np.arange(1, len(ranked) + 1) / len(ranked)
    passed = ranked <= thresh
    if np.any(passed):
        cutoff = ranked[np.where(passed)[0].max()]
        sig[valid] = pv <= cutoff
    return sig


def contiguous_sig_windows(
    sig_mask: np.ndarray,
    bin_centers: np.ndarray,
    bin_size: float,
    min_bins: int = 5,
) -> list[tuple[float, float]]:
    windows = []
    start = None
    for i, is_sig in enumerate(sig_mask):
        if is_sig and start is None:
            start = i
        elif (not is_sig) and start is not None:
            end = i - 1
            if end - start + 1 >= min_bins:
                windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
            start = None
    if start is not None:
        end = len(sig_mask) - 1
        if end - start + 1 >= min_bins:
            windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
    return windows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cluster amygdala/hippocampus single-unit time curves only")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--event-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--tmin", type=float, default=-0.5)
    p.add_argument("--tmax", type=float, default=2.0)
    p.add_argument("--bin-ms", type=float, default=10.0)
    p.add_argument("--smooth-ms", type=float, default=50.0)
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--min-events", type=int, default=30)
    p.add_argument("--min-spikes-in-window", type=int, default=20)
    p.add_argument("--response-win", type=float, nargs=2, default=(0.0, 1.0))
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def plot_group(ax, bin_centers: np.ndarray, bin_size: float, df: pd.DataFrame, curves: np.ndarray, title: str) -> None:
    colors = {0: "#1f77b4", 1: "#d62728"}
    cluster_curves = {}
    for c in [0, 1]:
        idx = df["cluster"].to_numpy() == c
        n = int(np.sum(idx))
        if n == 0:
            continue
        cluster_curves[c] = curves[idx]
        mean = np.mean(cluster_curves[c], axis=0)
        se = sem(cluster_curves[c])
        ax.plot(bin_centers, mean, color=colors[c], lw=2.2, label=f"Cluster {c} (n={n})")
        ax.fill_between(bin_centers, mean - se, mean + se, color=colors[c], alpha=0.18, linewidth=0)
    if 0 in cluster_curves and 1 in cluster_curves and len(cluster_curves[0]) >= 2 and len(cluster_curves[1]) >= 2:
        _, pvals = ttest_ind(cluster_curves[0], cluster_curves[1], axis=0, equal_var=False, nan_policy="omit")
        sig_mask = fdr_bh(pvals, alpha=0.05) & (bin_centers >= 0.0)
        for t0, t1 in contiguous_sig_windows(sig_mask, bin_centers, bin_size, min_bins=5):
            ax.axvspan(t0, t1, color="gold", alpha=0.16, linewidth=0)
    ax.axvline(0.0, color="k", lw=1.2, ls="--")
    ax.axhline(0.0, color="k", lw=0.8, ls=":")
    ax.set_title(title, fontproperties=font(16))
    ax.grid(True, alpha=0.15)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    np.random.seed(args.seed)
    events = load_events(args.event_csv)
    nwb_files = iter_nwb_files(args.data_dir)

    bin_s = args.bin_ms / 1000.0
    bin_edges = np.arange(args.tmin, args.tmax + bin_s, bin_s)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    smooth_sigma_bins = (args.smooth_ms / 1000.0) / max(bin_s, 1e-12)
    base_idx = np.where((bin_centers >= args.tmin) & (bin_centers < 0.0))[0]
    resp_idx = np.where((bin_centers >= args.response_win[0]) & (bin_centers < args.response_win[1]))[0]

    feat_rows: list[np.ndarray] = []
    meta_rows: list[dict[str, object]] = []

    for nwb_path in nwb_files:
        subject = infer_subject_id(nwb_path)
        sub_ev = events.loc[events["subject"] == subject].copy()
        if len(sub_ev) < args.min_events:
            continue
        onsets = sub_ev["onset"].astype(float).to_numpy()

        with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
            nwb = io.read()
            if nwb.units is None:
                continue
            units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            continue

        for unit_index, spike_times in enumerate(units["spike_times"].to_list()):
            region = unit_region(units, unit_index)
            if region not in {"杏仁核", "海马"}:
                continue

            st = np.asarray(spike_times, dtype=float)
            mat = unit_trial_rate_matrix(
                spike_times=st,
                onsets=onsets,
                bin_edges=bin_edges,
                tmin=args.tmin,
                tmax=args.tmax,
                smooth_sigma_bins=smooth_sigma_bins,
            )
            total_spk = int(np.sum(mat) * bin_s)
            if total_spk < args.min_spikes_in_window:
                continue

            curve = np.mean(mat, axis=0)
            curve_z = zscore_by_baseline(curve, base_idx)

            base_mean = float(np.mean(curve[base_idx]))
            resp_mean = float(np.mean(curve[resp_idx]))
            trial_delta = np.mean(mat[:, resp_idx], axis=1) - np.mean(mat[:, base_idx], axis=1)

            feat_rows.append(curve_z.astype(float))
            meta_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "unit_index": int(unit_index),
                    "region": region,
                    "n_events": int(len(onsets)),
                    "baseline_rate_hz": base_mean,
                    "response_rate_hz": resp_mean,
                    "delta_rate_hz": float(resp_mean - base_mean),
                    "trial_delta_median": float(np.median(trial_delta)),
                    "trial_delta_mean": float(np.mean(trial_delta)),
                }
            )

    if not feat_rows:
        raise RuntimeError("No amygdala/hippocampus units passed filters")

    x = np.vstack(feat_rows)
    meta = pd.DataFrame(meta_rows)
    k = int(max(2, min(args.k, x.shape[0])))

    _, labels = kmeans2(x, k=k, minit="points", iter=100)
    meta["cluster_raw"] = labels.astype(int)

    cluster_order = meta.groupby("cluster_raw")["delta_rate_hz"].median().sort_values().index.to_list()
    remap = {old: new for new, old in enumerate(cluster_order)}
    meta["cluster"] = meta["cluster_raw"].map(remap).astype(int)

    stats_rows = []
    proto_tbl = pd.DataFrame({"time_s": bin_centers})
    for c in range(k):
        idx = meta["cluster"].to_numpy() == c
        curves = x[idx]
        proto = np.mean(curves, axis=0)
        proto_sem = sem(curves)
        d = meta.loc[idx, "delta_rate_hz"].to_numpy(float)
        try:
            p_w = float(wilcoxon(d).pvalue) if len(d) >= 6 and not np.allclose(d, 0.0) else np.nan
        except ValueError:
            p_w = np.nan
        stats_rows.append(
            {
                "cluster": int(c),
                "n_units": int(np.sum(idx)),
                "delta_rate_median_hz": float(np.median(d)),
                "delta_rate_mean_hz": float(np.mean(d)),
                "wilcoxon_p_vs0": p_w,
                "prototype_peak_z": float(np.max(proto)),
                "prototype_trough_z": float(np.min(proto)),
            }
        )
        proto_tbl[f"proto_cluster_{c}"] = proto
        proto_tbl[f"sem_cluster_{c}"] = proto_sem

    pair_rows = []
    for c1 in range(k):
        for c2 in range(c1 + 1, k):
            d1 = meta.loc[meta["cluster"] == c1, "delta_rate_hz"].to_numpy(float)
            d2 = meta.loc[meta["cluster"] == c2, "delta_rate_hz"].to_numpy(float)
            p_mw = float(mannwhitneyu(d1, d2, alternative="two-sided").pvalue) if len(d1) >= 3 and len(d2) >= 3 else np.nan
            pair_rows.append(
                {
                    "cluster_a": int(c1),
                    "cluster_b": int(c2),
                    "median_delta_a": float(np.median(d1)),
                    "median_delta_b": float(np.median(d2)),
                    "mannwhitney_p": p_mw,
                }
            )

    unit_out = args.output_dir / "unit_timecurve_cluster_table_ah_only.csv"
    stats_out = args.output_dir / "unit_timecurve_cluster_stats_ah_only.csv"
    pair_out = args.output_dir / "unit_timecurve_cluster_pairwise_stats_ah_only.csv"
    proto_out = args.output_dir / "unit_timecurve_cluster_prototypes_ah_only.csv"
    count_out = args.output_dir / "unit_timecurve_cluster_region_counts_ah_only.csv"

    meta.to_csv(unit_out, index=False)
    pd.DataFrame(stats_rows).to_csv(stats_out, index=False)
    pd.DataFrame(pair_rows).to_csv(pair_out, index=False)
    proto_tbl.to_csv(proto_out, index=False)

    counts = (
        meta.groupby(["region", "cluster"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=["杏仁核", "海马"], fill_value=0)
    )
    counts["合计"] = counts.sum(axis=1)
    counts.loc["全部"] = counts.sum(axis=0)
    counts.to_csv(count_out)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), sharey=True)
    panels = [
        ("全部", meta.index.to_numpy()),
        ("杏仁核", meta.index[meta["region"] == "杏仁核"].to_numpy()),
        ("海马", meta.index[meta["region"] == "海马"].to_numpy()),
    ]
    for ax, (name, idx) in zip(axes, panels, strict=True):
        sub_meta = meta.iloc[idx].reset_index(drop=True)
        sub_x = x[idx]
        plot_group(ax, bin_centers, bin_s, sub_meta, sub_x, f"{name} (n={len(sub_meta)}个单元)")
    axes[0].set_ylabel("单元放电率（z，基线标准化）", fontproperties=font(14))
    for ax in axes:
        ax.set_xlabel("事件开始后的时间（秒）", fontproperties=font(14))
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(font(12))

    handles, leg_labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, leg_labels, loc="upper right", bbox_to_anchor=(0.98, 0.98), frameon=False)
    for text in leg.get_texts():
        text.set_fontproperties(font(12))
    fig.subplots_adjust(left=0.08, right=0.83, bottom=0.18, top=0.82, wspace=0.18)
    fig_out = args.output_dir / "unit_timecurve_cluster_prototypes_ah_only_by_region_1x3_chinese.png"
    fig.savefig(fig_out, dpi=300)
    plt.close(fig)

    print("region_cluster_counts")
    print(counts.to_string())
    print(f"saved {unit_out}")
    print(f"saved {stats_out}")
    print(f"saved {pair_out}")
    print(f"saved {proto_out}")
    print(f"saved {count_out}")
    print(f"saved {fig_out}")


if __name__ == "__main__":
    main()
