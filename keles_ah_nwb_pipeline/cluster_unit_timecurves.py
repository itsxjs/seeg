from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter1d
from scipy.stats import mannwhitneyu, wilcoxon

from ah_pipeline.nwb_io import iter_nwb_files, load_events


def infer_subject_id(nwb_path: Path) -> str:
    m_bids = re.search(r"(sub-[A-Za-z0-9]+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_bids:
        return m_bids.group(1).lower()
    m_num = re.search(r"(sub\d+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_num:
        return m_num.group(1).lower()
    return nwb_path.stem.lower()


def load_unit_spike_times(nwb_path: Path) -> list[np.ndarray]:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            return []
        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            return []
        out: list[np.ndarray] = []
        for st in units["spike_times"].to_list():
            out.append(np.asarray(st, dtype=float))
        return out


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cluster single-unit event-aligned time curves")
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
    p.add_argument("--max-files", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    np.random.seed(args.seed)

    events = load_events(args.event_csv)
    nwb_files = iter_nwb_files(args.data_dir)
    if args.max_files > 0:
        nwb_files = nwb_files[: args.max_files]

    bin_s = args.bin_ms / 1000.0
    bin_edges = np.arange(args.tmin, args.tmax + bin_s, bin_s)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    smooth_sigma_bins = (args.smooth_ms / 1000.0) / max(bin_s, 1e-12)

    base_idx = np.where((bin_centers >= args.tmin) & (bin_centers < 0.0))[0]
    resp_idx = np.where((bin_centers >= float(args.response_win[0])) & (bin_centers < float(args.response_win[1])))[0]
    if len(base_idx) == 0 or len(resp_idx) == 0:
        raise ValueError("Invalid baseline or response window with current bin settings")

    feat_rows: list[np.ndarray] = []
    meta_rows: list[dict[str, object]] = []

    for nwb_path in nwb_files:
        subject = infer_subject_id(nwb_path)
        sub_ev = events.loc[events["subject"] == subject].copy()
        if len(sub_ev) < int(args.min_events):
            continue
        onsets = sub_ev["onset"].astype(float).to_numpy()

        units = load_unit_spike_times(nwb_path)
        for u_idx, st in enumerate(units):
            mat = unit_trial_rate_matrix(
                spike_times=st,
                onsets=onsets,
                bin_edges=bin_edges,
                tmin=float(args.tmin),
                tmax=float(args.tmax),
                smooth_sigma_bins=float(smooth_sigma_bins),
            )
            if mat.size == 0:
                continue

            # Skip very sparse units to avoid unstable prototypes.
            total_spk = int(np.sum(mat) * bin_s)
            if total_spk < int(args.min_spikes_in_window):
                continue

            curve = np.mean(mat, axis=0)
            curve_z = zscore_by_baseline(curve, base_idx)

            base_mean = float(np.mean(curve[base_idx]))
            resp_mean = float(np.mean(curve[resp_idx]))
            delta_rate = resp_mean - base_mean

            trial_delta = np.mean(mat[:, resp_idx], axis=1) - np.mean(mat[:, base_idx], axis=1)

            feat_rows.append(curve_z.astype(float))
            meta_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "unit_index": int(u_idx),
                    "n_events": int(len(onsets)),
                    "baseline_rate_hz": base_mean,
                    "response_rate_hz": resp_mean,
                    "delta_rate_hz": float(delta_rate),
                    "trial_delta_median": float(np.median(trial_delta)),
                    "trial_delta_mean": float(np.mean(trial_delta)),
                    "trial_delta": trial_delta,
                }
            )

    if not feat_rows:
        raise RuntimeError("No units passed filters; try lowering --min-events or --min-spikes-in-window")

    X = np.vstack(feat_rows)
    n_units = X.shape[0]
    k = int(max(2, min(args.k, n_units)))

    # k-means on z-scored time curves.
    centroids, labels = kmeans2(X, k=k, minit="points", iter=100)
    labels = labels.astype(int)

    meta_df = pd.DataFrame(meta_rows)
    meta_df["cluster_raw"] = labels

    # Reorder clusters by median delta-rate (low->high), helps interpret antagonistic classes.
    cluster_order = (
        meta_df.groupby("cluster_raw")["delta_rate_hz"].median().sort_values().index.to_list()
    )
    remap = {old: new for new, old in enumerate(cluster_order)}
    meta_df["cluster"] = meta_df["cluster_raw"].map(remap).astype(int)

    # Recompute prototypes with sorted labels.
    protos = []
    proto_sem = []
    stats_rows: list[dict[str, object]] = []

    for c in range(k):
        idx = np.where(meta_df["cluster"].to_numpy() == c)[0]
        Xc = X[idx]
        proto = np.mean(Xc, axis=0)
        sem = np.std(Xc, axis=0, ddof=1) / max(np.sqrt(len(idx)), 1.0) if len(idx) > 1 else np.zeros_like(proto)
        protos.append(proto)
        proto_sem.append(sem)

        d = meta_df.iloc[idx]["delta_rate_hz"].to_numpy(dtype=float)
        if len(d) >= 6 and not np.allclose(d, 0.0):
            try:
                _st, p_w = wilcoxon(d)
                p_w = float(p_w)
            except ValueError:
                p_w = np.nan
        else:
            p_w = np.nan

        stats_rows.append(
            {
                "cluster": int(c),
                "n_units": int(len(idx)),
                "delta_rate_median_hz": float(np.median(d)) if len(d) else np.nan,
                "delta_rate_mean_hz": float(np.mean(d)) if len(d) else np.nan,
                "wilcoxon_p_vs0": p_w,
                "prototype_peak_z": float(np.max(proto)),
                "prototype_trough_z": float(np.min(proto)),
            }
        )

    stats_df = pd.DataFrame(stats_rows)

    # Pairwise cluster-separation stats on delta-rate.
    pair_rows: list[dict[str, object]] = []
    for c1 in range(k):
        for c2 in range(c1 + 1, k):
            d1 = meta_df.loc[meta_df["cluster"] == c1, "delta_rate_hz"].to_numpy(dtype=float)
            d2 = meta_df.loc[meta_df["cluster"] == c2, "delta_rate_hz"].to_numpy(dtype=float)
            if len(d1) >= 3 and len(d2) >= 3:
                _u, p_mw = mannwhitneyu(d1, d2, alternative="two-sided")
                p_mw = float(p_mw)
            else:
                p_mw = np.nan
            pair_rows.append(
                {
                    "cluster_a": int(c1),
                    "cluster_b": int(c2),
                    "median_delta_a": float(np.median(d1)) if len(d1) else np.nan,
                    "median_delta_b": float(np.median(d2)) if len(d2) else np.nan,
                    "mannwhitney_p": p_mw,
                }
            )

    pair_df = pd.DataFrame(pair_rows)

    # Build prototype table.
    proto_tbl = pd.DataFrame({"time_s": bin_centers})
    for c in range(k):
        proto_tbl[f"proto_cluster_{c}"] = protos[c]
        proto_tbl[f"sem_cluster_{c}"] = proto_sem[c]

    # Save files.
    unit_out = args.output_dir / "unit_timecurve_cluster_table.csv"
    stats_out = args.output_dir / "unit_timecurve_cluster_stats.csv"
    pair_out = args.output_dir / "unit_timecurve_cluster_pairwise_stats.csv"
    proto_out = args.output_dir / "unit_timecurve_cluster_prototypes.csv"

    meta_df = meta_df.drop(columns=["trial_delta"])
    meta_df.to_csv(unit_out, index=False)
    stats_df.to_csv(stats_out, index=False)
    pair_df.to_csv(pair_out, index=False)
    proto_tbl.to_csv(proto_out, index=False)

    # Plot prototypes.
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"]
    for c in range(k):
        color = colors[c % len(colors)]
        ax.plot(bin_centers, protos[c], color=color, lw=2, label=f"Cluster {c} (n={int((meta_df['cluster']==c).sum())})")
        ax.fill_between(bin_centers, protos[c] - proto_sem[c], protos[c] + proto_sem[c], color=color, alpha=0.2)

    ax.axvline(0.0, color="k", lw=1, ls="--")
    ax.axhline(0.0, color="k", lw=0.8, ls=":")
    ax.set_xlabel("Time from event (s)")
    ax.set_ylabel("Unit firing (z, baseline-normalized)")
    ax.set_title("Single-unit time-curve prototypes by cluster")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig_out = args.output_dir / "unit_timecurve_cluster_prototypes.png"
    fig.savefig(fig_out, dpi=160)
    plt.close(fig)

    # Additional antagonism summary for k=2.
    if k == 2:
        r = float(np.corrcoef(protos[0], protos[1])[0, 1])
    else:
        r = np.nan

    print("saved", unit_out)
    print("saved", stats_out)
    print("saved", pair_out)
    print("saved", proto_out)
    print("saved", fig_out)
    print("n_units", int(n_units), "k", int(k), "proto_corr_k2", r)


if __name__ == "__main__":
    main()
