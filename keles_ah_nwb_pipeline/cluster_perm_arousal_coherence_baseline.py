from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter
from scipy.ndimage import label
from scipy.stats import t


plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "Heiti TC",
    "Songti SC",
    "PingFang SC",
    "SimHei",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run baseline-corrected 2D cluster permutation on event-locked A-H coherence.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(
            "results/full_spectrum_arousal_all_subjects/connectivity_arousal_fullspectrum"
        ),
        help="Directory containing *_arousal_fullspectrum.mat files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "results/full_spectrum_arousal_all_subjects/connectivity_arousal_fullspectrum"
        ),
        help="Directory for cluster permutation outputs.",
    )
    parser.add_argument("--baseline-start", type=float, default=-0.5)
    parser.add_argument("--baseline-end", type=float, default=0.0)
    parser.add_argument("--analysis-start", type=float, default=0.0)
    parser.add_argument("--analysis-end", type=float, default=1.75)
    parser.add_argument("--n-perm", type=int, default=5000)
    parser.add_argument("--cluster-alpha", type=float, default=0.05)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument(
        "--plot-sigma",
        type=float,
        default=0.8,
        help="Gaussian sigma, in bins, applied only to the plotted group mean image.",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _collect_mats(input_dir: Path) -> list[Path]:
    mats = sorted(
        p for p in input_dir.glob("*_arousal_fullspectrum.mat")
        if not p.name.startswith("._")
    )
    if not mats:
        raise FileNotFoundError(f"No *_arousal_fullspectrum.mat files found in {input_dir}")
    return mats


def _load_coherence_stack(mat_paths: list[Path]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    stack: list[np.ndarray] = []
    used: list[str] = []
    ref_freqs = None
    ref_times = None

    for mat_path in mat_paths:
        mat = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
        coh_tf = np.asarray(mat["coh_tf"], dtype=float)
        freqs = np.asarray(mat["freqs_coh"], dtype=float).reshape(-1)
        times = np.asarray(mat["time_coh"], dtype=float).reshape(-1)

        if ref_freqs is None:
            ref_freqs = freqs
            ref_times = times

        if not np.allclose(freqs, ref_freqs) or not np.allclose(times, ref_times):
            continue

        if coh_tf.shape != (len(ref_freqs), len(ref_times)):
            continue

        stack.append(coh_tf)
        used.append(mat_path.name)

    if not stack or ref_freqs is None or ref_times is None:
        raise RuntimeError("No compatible coherence matrices were loaded")

    return np.stack(stack, axis=0), ref_freqs, ref_times, used


def _one_sample_t(values: np.ndarray) -> np.ndarray:
    n = values.shape[0]
    mean = np.nanmean(values, axis=0)
    sd = np.nanstd(values, axis=0, ddof=1)
    se = sd / np.sqrt(n)
    out = np.divide(mean, se, out=np.zeros_like(mean), where=se > 0)
    return out


def _cluster_masses(t_map: np.ndarray, threshold: float) -> tuple[np.ndarray, int]:
    supra = np.abs(t_map) >= threshold
    labels, n_labels = label(supra, structure=np.ones((3, 3), dtype=int))
    masses = np.zeros(n_labels, dtype=float)
    for cluster_id in range(1, n_labels + 1):
        masses[cluster_id - 1] = float(np.sum(np.abs(t_map[labels == cluster_id])))
    return labels, n_labels


def _run_cluster_permutation(
    values: np.ndarray,
    cluster_alpha: float,
    n_perm: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    n = values.shape[0]
    if n < 3:
        raise ValueError("Cluster permutation requires at least 3 observations")

    threshold = float(t.ppf(1.0 - cluster_alpha / 2.0, df=n - 1))
    t_obs = _one_sample_t(values)
    labels_obs, n_obs = _cluster_masses(t_obs, threshold)

    obs_masses = np.zeros(n_obs, dtype=float)
    for cluster_id in range(1, n_obs + 1):
        obs_masses[cluster_id - 1] = float(np.sum(np.abs(t_obs[labels_obs == cluster_id])))

    rng = np.random.default_rng(seed)
    max_masses = np.zeros(n_perm, dtype=float)
    for perm_idx in range(n_perm):
        signs = rng.choice(np.array([-1.0, 1.0]), size=(n, 1, 1), replace=True)
        t_perm = _one_sample_t(values * signs)
        labels_perm, n_perm_clusters = _cluster_masses(t_perm, threshold)
        if n_perm_clusters:
            max_masses[perm_idx] = max(
                float(np.sum(np.abs(t_perm[labels_perm == cluster_id])))
                for cluster_id in range(1, n_perm_clusters + 1)
            )

    pvals = np.ones(n_obs, dtype=float)
    for idx, mass in enumerate(obs_masses):
        pvals[idx] = (1.0 + np.sum(max_masses >= mass)) / (n_perm + 1.0)

    return t_obs, labels_obs, obs_masses, pvals, threshold


def _write_outputs(
    output_dir: Path,
    values: np.ndarray,
    freqs: np.ndarray,
    times: np.ndarray,
    baseline_times: np.ndarray,
    used: list[str],
    t_obs: np.ndarray,
    labels: np.ndarray,
    masses: np.ndarray,
    pvals: np.ndarray,
    threshold: float,
    args: argparse.Namespace,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | int]] = []
    sig_mask = np.zeros_like(t_obs, dtype=bool)
    for cluster_id, (mass, pval) in enumerate(zip(masses, pvals, strict=True), start=1):
        mask = labels == cluster_id
        if pval < args.alpha:
            sig_mask |= mask
        rows.append(
            {
                "cluster_id": cluster_id,
                "p_cluster": float(pval),
                "cluster_mass_abs_t": float(mass),
                "n_bins": int(np.sum(mask)),
                "freq_min_hz": float(np.min(freqs[np.any(mask, axis=1)])),
                "freq_max_hz": float(np.max(freqs[np.any(mask, axis=1)])),
                "time_min_s": float(np.min(times[np.any(mask, axis=0)])),
                "time_max_s": float(np.max(times[np.any(mask, axis=0)])),
                "mean_delta_coherence": float(np.nanmean(np.nanmean(values, axis=0)[mask])),
                "max_abs_t": float(np.nanmax(np.abs(t_obs[mask]))),
            }
        )

    clusters_csv = output_dir / "arousal_coherence_baseline_cluster_permutation_clusters.csv"
    pd.DataFrame(rows).sort_values(["p_cluster", "cluster_id"]).to_csv(clusters_csv, index=False)

    mean_delta = np.nanmean(values, axis=0)
    plot_delta = gaussian_filter(mean_delta, sigma=args.plot_sigma) if args.plot_sigma > 0 else mean_delta
    extent = [float(times.min()), float(times.max()), float(freqs.min()), float(freqs.max())]
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=220)
    lim = float(np.nanmax(np.abs(plot_delta)))
    im = ax.imshow(
        plot_delta,
        aspect="auto",
        origin="lower",
        extent=extent,
        cmap="RdBu_r",
        vmin=-lim,
        vmax=lim,
        interpolation="nearest",
    )
    if np.any(sig_mask):
        ax.contour(
            times,
            freqs,
            sig_mask.astype(float),
            levels=[0.5],
            colors="black",
            linewidths=1.0,
        )
    ax.axvline(0, color="#333333", lw=1.0, ls="--")
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("频率 (Hz)")
    ax.set_title("事件锁定 A-H 相干性变化（相对基线）")
    fig.colorbar(im, ax=ax, label="Delta coherence")
    fig.tight_layout()
    out_png = output_dir / "arousal_coherence_baseline_cluster_permutation.png"
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    summary = {
        "n_observations": len(used),
        "observation_unit": "NWB run",
        "used_files": used,
        "baseline_window_s": [args.baseline_start, args.baseline_end],
        "actual_baseline_time_centers_s": [
            float(baseline_times.min()),
            float(baseline_times.max()),
        ],
        "analysis_window_s": [args.analysis_start, args.analysis_end],
        "n_permutations": args.n_perm,
        "cluster_forming_alpha_two_sided": args.cluster_alpha,
        "cluster_alpha": args.alpha,
        "t_threshold_abs": threshold,
        "n_observed_clusters": int(len(masses)),
        "n_significant_clusters": int(np.sum(pvals < args.alpha)),
        "plot_gaussian_sigma_bins": args.plot_sigma,
        "plot_smoothing_note": "Gaussian smoothing is applied only to the displayed group mean image, not to cluster statistics.",
        "clusters_csv": str(clusters_csv),
        "figure_png": str(out_png),
    }
    with (output_dir / "arousal_coherence_baseline_cluster_permutation_summary.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    mats = _collect_mats(args.input_dir)
    coh_stack, freqs, times_all, used = _load_coherence_stack(mats)

    baseline_mask = (times_all >= args.baseline_start) & (times_all < args.baseline_end)
    analysis_mask = (times_all >= args.analysis_start) & (times_all <= args.analysis_end)
    if not np.any(baseline_mask):
        raise ValueError("No baseline samples found")
    if not np.any(analysis_mask):
        raise ValueError("No analysis samples found")

    baseline = np.nanmean(coh_stack[:, :, baseline_mask], axis=2, keepdims=True)
    delta = coh_stack[:, :, analysis_mask] - baseline
    times = times_all[analysis_mask]
    baseline_times = times_all[baseline_mask]

    t_obs, labels, masses, pvals, threshold = _run_cluster_permutation(
        delta,
        cluster_alpha=args.cluster_alpha,
        n_perm=args.n_perm,
        seed=args.seed,
    )
    _write_outputs(
        args.output_dir,
        delta,
        freqs,
        times,
        baseline_times,
        used,
        t_obs,
        labels,
        masses,
        pvals,
        threshold,
        args,
    )


if __name__ == "__main__":
    main()
