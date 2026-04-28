from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ttest_rel


def _fdr_bh(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    out = np.zeros_like(p, dtype=bool)
    ok = np.isfinite(p)
    if not np.any(ok):
        return out

    idx = np.where(ok)[0]
    pv = p[idx]
    order = np.argsort(pv)
    pv_sorted = pv[order]
    ranks = np.arange(1, len(pv_sorted) + 1)
    thresh = alpha * ranks / len(pv_sorted)
    passed = pv_sorted <= thresh
    if not np.any(passed):
        return out

    kmax = np.max(np.where(passed)[0])
    cutoff = pv_sorted[kmax]
    out[idx] = pv <= cutoff
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot summary figures for arousal-based connectivity results")
    p.add_argument(
        "--input-dir",
        type=Path,
        default=Path("results/sgc_arousal_all_subjects"),
        help="Directory containing combined_arousal_sgc.csv and combined_arousal_coherence.csv",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for figures (default: input-dir)",
    )
    return p.parse_args()


def _prepare_subject_level(sgc_df: pd.DataFrame, coh_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sgc_clean = sgc_df.copy()
    sgc_clean["A_to_H_gc"] = pd.to_numeric(sgc_clean["A_to_H_gc"], errors="coerce")
    sgc_clean["H_to_A_gc"] = pd.to_numeric(sgc_clean["H_to_A_gc"], errors="coerce")

    # Aggregate at subject-band level to avoid inflation from pair/trial counts.
    subj_band_sgc = (
        sgc_clean.groupby(["subject", "band"], as_index=False)[["A_to_H_gc", "H_to_A_gc"]]
        .mean(numeric_only=True)
        .dropna(subset=["A_to_H_gc", "H_to_A_gc"], how="all")
    )

    coh_clean = coh_df.copy()
    coh_clean["A_H_coherence"] = pd.to_numeric(coh_clean["A_H_coherence"], errors="coerce")
    subj_band_coh = (
        coh_clean.groupby(["subject", "band"], as_index=False)["A_H_coherence"]
        .mean()
        .dropna(subset=["A_H_coherence"])
    )

    return subj_band_sgc, subj_band_coh


def _band_order(bands: list[str]) -> list[str]:
    preferred = ["delta", "theta", "alpha", "beta", "gamma"]
    found = [b for b in preferred if b in bands]
    extras = sorted([b for b in bands if b not in preferred])
    return found + extras


def _plot_sgc_direction(subj_band_sgc: pd.DataFrame, output_png: Path) -> dict:
    bands = _band_order(sorted(subj_band_sgc["band"].dropna().unique().tolist()))
    if not bands:
        raise ValueError("No valid bands found in sGC data")

    x = np.arange(len(bands))
    width = 0.36

    mean_a = []
    mean_h = []
    sem_a = []
    sem_h = []
    pvals = []
    n_subj = []

    for b in bands:
        part = subj_band_sgc[subj_band_sgc["band"] == b]
        a = part["A_to_H_gc"].to_numpy(dtype=float)
        h = part["H_to_A_gc"].to_numpy(dtype=float)
        ok = np.isfinite(a) & np.isfinite(h)
        a = a[ok]
        h = h[ok]

        n = len(a)
        n_subj.append(int(n))
        if n == 0:
            mean_a.append(np.nan)
            mean_h.append(np.nan)
            sem_a.append(np.nan)
            sem_h.append(np.nan)
            pvals.append(np.nan)
            continue

        mean_a.append(float(np.mean(a)))
        mean_h.append(float(np.mean(h)))
        sem_a.append(float(np.std(a, ddof=0) / np.sqrt(n)))
        sem_h.append(float(np.std(h, ddof=0) / np.sqrt(n)))

        if n >= 3:
            _, p = ttest_rel(a, h, nan_policy="omit")
            pvals.append(float(p))
        else:
            pvals.append(np.nan)

    pvals_arr = np.array(pvals, dtype=float)
    sig_fdr = _fdr_bh(pvals_arr, alpha=0.05)

    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=180)
    bars_a = ax.bar(x - width / 2, mean_a, width=width, yerr=sem_a, capsize=4, color="#c44e52", alpha=0.88, label="A→H")
    bars_h = ax.bar(x + width / 2, mean_h, width=width, yerr=sem_h, capsize=4, color="#4c72b0", alpha=0.88, label="H→A")

    y_max = np.nanmax(np.concatenate([np.array(mean_a) + np.array(sem_a), np.array(mean_h) + np.array(sem_h)]))
    if not np.isfinite(y_max):
        y_max = 1.0

    for i, b in enumerate(bands):
        p_txt = "n/a" if not np.isfinite(pvals_arr[i]) else f"p={pvals_arr[i]:.3g}"
        n_txt = f"n={n_subj[i]}"
        sig_txt = "*" if sig_fdr[i] else ""
        ax.text(x[i], y_max * 1.06, f"{n_txt}\n{p_txt}{sig_txt}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(bands)
    ax.set_ylabel("Granger Causality (subject-mean)")
    ax.set_title("Arousal Segments: Directional sGC by Frequency Band")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper right")
    ax.set_ylim(0, y_max * 1.25)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    return {
        "bands": bands,
        "n_subjects_per_band": n_subj,
        "pvals_a2h_vs_h2a": [None if not np.isfinite(v) else float(v) for v in pvals_arr],
        "sig_fdr_q05": sig_fdr.astype(bool).tolist(),
        "figure": str(output_png),
    }


def _plot_coherence(subj_band_coh: pd.DataFrame, output_png: Path) -> dict:
    bands = _band_order(sorted(subj_band_coh["band"].dropna().unique().tolist()))
    if not bands:
        raise ValueError("No valid bands found in coherence data")

    means = []
    sems = []
    ns = []
    for b in bands:
        part = subj_band_coh[subj_band_coh["band"] == b]["A_H_coherence"].to_numpy(dtype=float)
        part = part[np.isfinite(part)]
        ns.append(int(len(part)))
        if len(part) == 0:
            means.append(np.nan)
            sems.append(np.nan)
        else:
            means.append(float(np.mean(part)))
            sems.append(float(np.std(part, ddof=0) / np.sqrt(len(part))))

    x = np.arange(len(bands))

    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=180)
    bars = ax.bar(x, means, yerr=sems, capsize=5, color="#55a868", alpha=0.9)

    for i in range(len(bands)):
        ax.text(x[i], (means[i] if np.isfinite(means[i]) else 0) + (sems[i] if np.isfinite(sems[i]) else 0) + 0.01, f"n={ns[i]}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(bands)
    ax.set_ylabel("A-H Coherence (subject-mean)")
    ax.set_title("Arousal Segments: A-H Coherence by Frequency Band")
    ax.grid(axis="y", alpha=0.22)
    y_max = np.nanmax(np.array(means) + np.array(sems))
    if not np.isfinite(y_max):
        y_max = 1.0
    ax.set_ylim(0, y_max * 1.25)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    return {
        "bands": bands,
        "n_subjects_per_band": ns,
        "mean_coherence": [None if not np.isfinite(v) else float(v) for v in means],
        "figure": str(output_png),
    }


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir if args.output_dir is not None else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    sgc_csv = input_dir / "combined_arousal_sgc.csv"
    coh_csv = input_dir / "combined_arousal_coherence.csv"

    if not sgc_csv.exists():
        raise FileNotFoundError(f"Missing file: {sgc_csv}")
    if not coh_csv.exists():
        raise FileNotFoundError(f"Missing file: {coh_csv}")

    sgc_df = pd.read_csv(sgc_csv)
    coh_df = pd.read_csv(coh_csv)

    subj_band_sgc, subj_band_coh = _prepare_subject_level(sgc_df, coh_df)

    sgc_png = output_dir / "arousal_sgc_direction_by_band.png"
    coh_png = output_dir / "arousal_coherence_by_band.png"

    sgc_stats = _plot_sgc_direction(subj_band_sgc, sgc_png)
    coh_stats = _plot_coherence(subj_band_coh, coh_png)

    summary = {
        "input_dir": str(input_dir),
        "n_rows_sgc": int(len(sgc_df)),
        "n_rows_coherence": int(len(coh_df)),
        "n_subject_band_rows_sgc": int(len(subj_band_sgc)),
        "n_subject_band_rows_coherence": int(len(subj_band_coh)),
        "sgc": sgc_stats,
        "coherence": coh_stats,
    }

    summary_path = output_dir / "arousal_plot_stats.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"saved {sgc_png}")
    print(f"saved {coh_png}")
    print(f"saved {summary_path}")


if __name__ == "__main__":
    main()
