from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy import stats
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter1d

from ah_pipeline.nwb_io import iter_nwb_files
from cluster_unit_timecurves_ah_only import (
    fdr_bh,
    font,
    unit_region,
    unit_trial_rate_matrix,
    zscore_by_baseline,
)


DEFAULT_OUTPUT_DIR = Path("results/final_score_extreme_clusters")


def infer_subject_id(nwb_path: Path) -> str:
    m_bids = re.search(r"(sub-[A-Za-z0-9]+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_bids:
        return m_bids.group(1).lower()
    m_num = re.search(r"(sub\d+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_num:
        return m_num.group(1).lower()
    return nwb_path.stem.lower()


def sem(curves: np.ndarray) -> np.ndarray:
    if curves.shape[0] <= 1:
        return np.zeros(curves.shape[1])
    return np.std(curves, axis=0, ddof=1) / np.sqrt(curves.shape[0])


def trimmed_mean_sem(curves: np.ndarray, trim_frac: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    curves = np.asarray(curves)
    if curves.shape[0] == 0:
        return np.zeros(curves.shape[1]), np.zeros(curves.shape[1])
    k = int(np.floor(curves.shape[0] * trim_frac))
    sorted_curves = np.sort(curves, axis=0)
    if 2 * k < curves.shape[0]:
        trimmed = sorted_curves[k : curves.shape[0] - k]
    else:
        trimmed = sorted_curves
    return np.mean(trimmed, axis=0), sem(trimmed)


def contiguous_sig_windows(
    sig_mask: np.ndarray,
    bin_centers: np.ndarray,
    bin_size: float,
    min_bins: int = 5,
) -> list[tuple[float, float]]:
    windows: list[tuple[float, float]] = []
    start = None
    for i, is_sig in enumerate(sig_mask):
        if is_sig and start is None:
            start = i
        elif not is_sig and start is not None:
            end = i - 1
            if end - start + 1 >= min_bins:
                windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
            start = None
    if start is not None:
        end = len(sig_mask) - 1
        if end - start + 1 >= min_bins:
            windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
    return windows


def choose_low_events(window_scores: pd.DataFrame, n_events: int) -> pd.DataFrame:
    selected: list[pd.Series] = []
    intervals: list[tuple[float, float]] = []

    for _idx, row in window_scores.sort_values("final_score", ascending=True).iterrows():
        start = float(row["start_sec"])
        end = float(row["end_sec"])
        overlaps = any(start < old_end and end > old_start for old_start, old_end in intervals)
        if overlaps:
            continue
        selected.append(row)
        intervals.append((start, end))
        if len(selected) == n_events:
            break

    if len(selected) < n_events:
        raise ValueError(f"Only found {len(selected)} non-overlapping low-score events; need {n_events}.")
    return pd.DataFrame(selected).reset_index(drop=True)


def load_extreme_events(arousal_segments_csv: Path, window_scores_csv: Path) -> pd.DataFrame:
    high = pd.read_csv(arousal_segments_csv).copy()
    windows = pd.read_csv(window_scores_csv).copy()
    required = {"start_sec", "end_sec", "center_sec", "final_score"}
    missing_high = required.difference(high.columns)
    missing_windows = required.difference(windows.columns)
    if missing_high:
        raise ValueError(f"High-score segment file missing columns: {sorted(missing_high)}")
    if missing_windows:
        raise ValueError(f"Window-score file missing columns: {sorted(missing_windows)}")

    low = choose_low_events(windows, len(high))
    high["score_group"] = "high_final_score"
    low["score_group"] = "low_final_score"
    cols = [
        "score_group",
        "start_sec",
        "end_sec",
        "center_sec",
        "final_score",
        "arousal_score",
        "confidence",
        "audio_salience",
    ]
    cols = [c for c in cols if c in high.columns or c in low.columns]
    return pd.concat([high, low], ignore_index=True, sort=False)[cols].sort_values(
        ["score_group", "center_sec"]
    )


def compute_sig_windows(
    high_curves: np.ndarray,
    low_curves: np.ndarray,
    bin_centers: np.ndarray,
    bin_size: float,
) -> list[tuple[float, float]]:
    if high_curves.shape[0] < 2:
        return []
    _stat, pvals = stats.ttest_rel(high_curves, low_curves, axis=0, nan_policy="omit")
    sig_mask = fdr_bh(pvals, alpha=0.05) & (bin_centers >= 0.0)
    return contiguous_sig_windows(sig_mask, bin_centers, bin_size, min_bins=5)


def plot_high_low_panel(
    ax,
    bin_centers: np.ndarray,
    bin_size: float,
    high_curves: np.ndarray,
    low_curves: np.ndarray,
    title: str,
    title_size: float = 16,
) -> None:
    n_units = high_curves.shape[0]
    if n_units == 0:
        ax.set_title(f"{title} (n=0)", fontproperties=font(title_size))
        ax.axvline(0, color="black", linestyle="--", linewidth=1.2)
        ax.grid(True, alpha=0.15)
        return

    high_mean, high_sem = trimmed_mean_sem(high_curves, trim_frac=0.2)
    low_mean, low_sem = trimmed_mean_sem(low_curves, trim_frac=0.2)
    ax.plot(bin_centers, high_mean, color="crimson", linewidth=2.2, label="高 final score")
    ax.fill_between(bin_centers, high_mean - high_sem, high_mean + high_sem, color="crimson", alpha=0.12)
    ax.plot(bin_centers, low_mean, color="royalblue", linewidth=2.2, label="低 final score")
    ax.fill_between(bin_centers, low_mean - low_sem, low_mean + low_sem, color="royalblue", alpha=0.12)

    for i, (t0, t1) in enumerate(compute_sig_windows(high_curves, low_curves, bin_centers, bin_size)):
        ax.axvspan(t0, t1, color="gold", alpha=0.16, label="FDR<0.05" if i == 0 else None)

    ax.axvline(0.0, color="black", linestyle="--", linewidth=1.2)
    ax.axhline(0.0, color="black", linestyle=":", linewidth=0.8)
    ax.set_title(f"{title} (n={n_units}个单元)", fontproperties=font(title_size))
    ax.grid(True, alpha=0.15)


def save_cluster_plot(
    path: Path,
    clusters: np.ndarray,
    bin_centers: np.ndarray,
    bin_size: float,
    y_high: np.ndarray,
    y_low: np.ndarray,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    for c in [0, 1]:
        idx = clusters == c
        plot_high_low_panel(axes[c], bin_centers, bin_size, y_high[idx], y_low[idx], f"Cluster {c}")
        axes[c].set_xlabel("事件开始后的时间（秒）", fontproperties=font(14))
    axes[0].set_ylabel("高-低事件单元反应曲线（z，基线标准化）", fontproperties=font(14))
    handles = [
        Line2D([0], [0], color="crimson", lw=2.5, label="高 final score"),
        Line2D([0], [0], color="royalblue", lw=2.5, label="低 final score"),
        Patch(facecolor="gold", edgecolor="gold", alpha=0.16, label="FDR<0.05"),
    ]
    leg = fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.98, 0.98), frameon=False)
    for text in leg.get_texts():
        text.set_fontproperties(font(12))
    fig.suptitle("最高与最低 final score 事件的杏仁核-海马单元反应聚类", fontproperties=font(20))
    fig.tight_layout(rect=(0, 0, 0.94, 0.92))
    fig.savefig(path, dpi=300)
    plt.close(fig)


def save_region_plot(
    path: Path,
    clusters: np.ndarray,
    bin_centers: np.ndarray,
    bin_size: float,
    y_high: np.ndarray,
    y_low: np.ndarray,
    meta: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(16, 8), sharex=True, sharey=True)
    columns = [("全部", None), ("杏仁核", "杏仁核"), ("海马", "海马")]
    region_arr = meta["region"].to_numpy()
    for row, c in enumerate([0, 1]):
        for col, (title, region) in enumerate(columns):
            if region is None:
                idx = clusters == c
            else:
                idx = (clusters == c) & (region_arr == region)
            plot_high_low_panel(
                axes[row, col],
                bin_centers,
                bin_size,
                y_high[idx],
                y_low[idx],
                f"Cluster {c} - {title}",
                title_size=13,
            )
    for ax in axes[-1, :]:
        ax.set_xlabel("事件开始后的时间（秒）", fontproperties=font(12))
    for ax in axes[:, 0]:
        ax.set_ylabel("z 分数", fontproperties=font(12))
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cluster amygdala/hippocampus NWB unit responses to high vs matched low final-score events."
    )
    p.add_argument("--data-dir", type=Path, default=Path("data/000623"))
    p.add_argument(
        "--arousal-segments-csv",
        type=Path,
        default=Path("results/arousal_short_local_3b_fix_full/arousal_segments.csv"),
    )
    p.add_argument(
        "--window-scores-csv",
        type=Path,
        default=Path("results/arousal_short_local_3b_fix_full/window_scores.csv"),
    )
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--tmin", type=float, default=-0.5)
    p.add_argument("--tmax", type=float, default=2.0)
    p.add_argument("--bin-ms", type=float, default=10.0)
    p.add_argument("--smooth-ms", type=float, default=50.0)
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--min-spikes-in-window", type=int, default=20)
    p.add_argument("--response-win", type=float, nargs=2, default=(0.0, 1.0))
    p.add_argument("--max-files", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(args.seed)

    events = load_extreme_events(args.arousal_segments_csv, args.window_scores_csv)
    event_out = args.output_dir / "final_score_extreme_events.csv"
    events.to_csv(event_out, index=False)

    high_onsets = events.loc[events["score_group"] == "high_final_score", "center_sec"].to_numpy(float)
    low_onsets = events.loc[events["score_group"] == "low_final_score", "center_sec"].to_numpy(float)

    bin_s = args.bin_ms / 1000.0
    bin_edges = np.arange(args.tmin, args.tmax + bin_s, bin_s)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    smooth_sigma_bins = (args.smooth_ms / 1000.0) / max(bin_s, 1e-12)
    base_idx = np.where((bin_centers >= args.tmin) & (bin_centers < 0.0))[0]
    resp_idx = np.where((bin_centers >= args.response_win[0]) & (bin_centers < args.response_win[1]))[0]
    if len(base_idx) == 0 or len(resp_idx) == 0:
        raise ValueError("Invalid baseline or response window with current bin settings")

    nwb_files = iter_nwb_files(args.data_dir)
    if args.max_files > 0:
        nwb_files = nwb_files[: args.max_files]

    feat_rows: list[np.ndarray] = []
    high_rows: list[np.ndarray] = []
    low_rows: list[np.ndarray] = []
    meta_rows: list[dict[str, object]] = []
    session_rows: list[dict[str, object]] = []

    for nwb_path in nwb_files:
        subject = infer_subject_id(nwb_path)
        n_units_seen = 0
        n_ah_units = 0
        n_kept = 0
        with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
            nwb = io.read()
            if nwb.units is None:
                session_rows.append(
                    {"subject": subject, "nwb_file": str(nwb_path), "n_units": 0, "n_ah_units": 0, "n_kept": 0}
                )
                continue
            units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            continue

        for unit_index, spike_times in enumerate(units["spike_times"].to_list()):
            n_units_seen += 1
            region = unit_region(units, unit_index)
            if region not in {"杏仁核", "海马"}:
                continue
            n_ah_units += 1

            st = np.asarray(spike_times, dtype=float)
            high_mat = unit_trial_rate_matrix(
                spike_times=st,
                onsets=high_onsets,
                bin_edges=bin_edges,
                tmin=float(args.tmin),
                tmax=float(args.tmax),
                smooth_sigma_bins=float(smooth_sigma_bins),
            )
            low_mat = unit_trial_rate_matrix(
                spike_times=st,
                onsets=low_onsets,
                bin_edges=bin_edges,
                tmin=float(args.tmin),
                tmax=float(args.tmax),
                smooth_sigma_bins=float(smooth_sigma_bins),
            )
            total_spk = int((np.sum(high_mat) + np.sum(low_mat)) * bin_s)
            if total_spk < int(args.min_spikes_in_window):
                continue

            high_curve = np.mean(high_mat, axis=0)
            low_curve = np.mean(low_mat, axis=0)
            high_z = zscore_by_baseline(high_curve, base_idx)
            low_z = zscore_by_baseline(low_curve, base_idx)
            diff_z = high_z - low_z
            max_abs_diff = float(np.max(np.abs(diff_z)))
            if max_abs_diff <= 0.01:
                continue

            feat_rows.append((diff_z / (max_abs_diff + 1e-6)).astype(float))
            high_rows.append(high_z.astype(float))
            low_rows.append(low_z.astype(float))

            high_resp = np.mean(high_mat[:, resp_idx], axis=1) - np.mean(high_mat[:, base_idx], axis=1)
            low_resp = np.mean(low_mat[:, resp_idx], axis=1) - np.mean(low_mat[:, base_idx], axis=1)
            n_kept += 1
            meta_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "unit_index": int(unit_index),
                    "region": region,
                    "n_high_events": int(len(high_onsets)),
                    "n_low_events": int(len(low_onsets)),
                    "total_spikes_in_window": int(total_spk),
                    "high_response_delta_hz": float(np.mean(high_resp)),
                    "low_response_delta_hz": float(np.mean(low_resp)),
                    "high_minus_low_mean_0_1s": float(np.mean(high_resp) - np.mean(low_resp)),
                    "max_abs_high_low_diff_z": max_abs_diff,
                }
            )

        session_rows.append(
            {
                "subject": subject,
                "nwb_file": str(nwb_path),
                "n_units": int(n_units_seen),
                "n_ah_units": int(n_ah_units),
                "n_kept": int(n_kept),
            }
        )

    if not feat_rows:
        raise RuntimeError("No amygdala/hippocampus units passed filters")

    x = np.vstack(feat_rows)
    y_high = np.vstack(high_rows)
    y_low = np.vstack(low_rows)
    k = int(max(2, min(args.k, x.shape[0])))

    _centroids, labels = kmeans2(x, k=k, minit="points", iter=100)
    meta = pd.DataFrame(meta_rows)
    meta["cluster_raw"] = labels.astype(int)
    cluster_order = meta.groupby("cluster_raw")["high_minus_low_mean_0_1s"].median().sort_values().index.to_list()
    remap = {old: new for new, old in enumerate(cluster_order)}
    meta["cluster"] = meta["cluster_raw"].map(remap).astype(int)
    clusters = meta["cluster"].to_numpy()

    unit_out = args.output_dir / "final_score_extreme_cluster_unit_table.csv"
    meta.to_csv(unit_out, index=False)

    session_out = args.output_dir / "final_score_extreme_session_qc.csv"
    pd.DataFrame(session_rows).to_csv(session_out, index=False)

    count_table = (
        meta.groupby(["region", "cluster"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=["杏仁核", "海马"], fill_value=0)
    )
    count_table["合计"] = count_table.sum(axis=1)
    count_table.loc["全部"] = count_table.sum(axis=0)
    count_out = args.output_dir / "final_score_extreme_cluster_region_counts.csv"
    count_table.to_csv(count_out)

    proto_rows: list[dict[str, float | int]] = []
    for c in range(k):
        idx = clusters == c
        high_mean, high_sem = trimmed_mean_sem(y_high[idx], trim_frac=0.2)
        low_mean, low_sem = trimmed_mean_sem(y_low[idx], trim_frac=0.2)
        diff_mean, diff_sem = trimmed_mean_sem(x[idx], trim_frac=0.2)
        for t, hm, hs, lm, ls, dm, ds in zip(
            bin_centers, high_mean, high_sem, low_mean, low_sem, diff_mean, diff_sem, strict=True
        ):
            proto_rows.append(
                {
                    "cluster": int(c),
                    "time_sec": float(t),
                    "high_mean_z": float(hm),
                    "high_sem_z": float(hs),
                    "low_mean_z": float(lm),
                    "low_sem_z": float(ls),
                    "high_minus_low_mean_z": float(dm),
                    "high_minus_low_sem_z": float(ds),
                }
            )
    proto_out = args.output_dir / "final_score_extreme_cluster_prototypes.csv"
    pd.DataFrame(proto_rows).to_csv(proto_out, index=False)

    plot_out = args.output_dir / "final_score_extreme_clusters_raw_ifr.png"
    save_cluster_plot(plot_out, clusters, bin_centers, bin_s, y_high, y_low)
    region_plot_out = args.output_dir / "final_score_extreme_clusters_by_region_2x3.png"
    save_region_plot(region_plot_out, clusters, bin_centers, bin_s, y_high, y_low, meta)

    summary = {
        "n_high_events": int(len(high_onsets)),
        "n_low_events": int(len(low_onsets)),
        "high_final_score_min": float(events.loc[events["score_group"] == "high_final_score", "final_score"].min()),
        "high_final_score_max": float(events.loc[events["score_group"] == "high_final_score", "final_score"].max()),
        "low_final_score_min": float(events.loc[events["score_group"] == "low_final_score", "final_score"].min()),
        "low_final_score_max": float(events.loc[events["score_group"] == "low_final_score", "final_score"].max()),
        "n_nwb_files": int(len(nwb_files)),
        "n_ah_units_seen": int(sum(row["n_ah_units"] for row in session_rows)),
        "n_units_clustered": int(len(meta)),
        "cluster_counts": {str(k_): int(v) for k_, v in meta["cluster"].value_counts().sort_index().items()},
        "region_cluster_counts": count_table.astype(int).to_dict(),
        "min_spikes_in_window": int(args.min_spikes_in_window),
        "cluster_feature": "per-unit normalized high_z_minus_low_z time curve",
        "outputs": {
            "events": str(event_out),
            "unit_table": str(unit_out),
            "session_qc": str(session_out),
            "region_counts": str(count_out),
            "prototypes": str(proto_out),
            "cluster_plot": str(plot_out),
            "region_plot": str(region_plot_out),
        },
    }
    summary_out = args.output_dir / "final_score_extreme_cluster_summary.json"
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Final-score extreme AH-only NWB unit clustering complete.")
    print(f"Events: {event_out}")
    print(f"Unit table: {unit_out}")
    print(f"Session QC: {session_out}")
    print(f"Region counts: {count_out}")
    print(f"Cluster plot: {plot_out}")
    print(f"Region plot: {region_plot_out}")
    print(f"Summary: {summary_out}")
    print("\nCluster-region counts:")
    print(count_table.to_string())


if __name__ == "__main__":
    main()
