from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.stats import ttest_rel

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


BANDS = [
    ("delta", "δ频段 (2-4 Hz)", 2.0, 4.0),
    ("theta", "θ频段 (4-8 Hz)", 4.0, 8.0),
    ("alpha", "α频段 (8-13 Hz)", 8.0, 13.0),
    ("beta", "β频段 (13-30 Hz)", 13.0, 30.0),
    ("gamma", "γ频段 (30-45 Hz)", 30.0, 45.0),
]


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
    passed = pv_sorted <= alpha * ranks / len(pv_sorted)
    if not np.any(passed):
        return out

    cutoff = pv_sorted[np.max(np.where(passed)[0])]
    out[idx] = pv <= cutoff
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize arousal full-spectrum sGC into five standard frequency bands.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("results/full_spectrum_arousal_all_subjects/connectivity_arousal_fullspectrum"),
        help="Directory containing *_arousal_fullspectrum.mat files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to input-dir.",
    )
    return parser.parse_args()


def _collect_rows(input_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    mat_paths = sorted(p for p in input_dir.glob("*_arousal_fullspectrum.mat") if not p.name.startswith("._"))
    if not mat_paths:
        raise FileNotFoundError(f"No *_arousal_fullspectrum.mat files found in {input_dir}")

    for mat_path in mat_paths:
        mat = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
        freqs = np.asarray(mat["freqs_gc"], dtype=float).reshape(-1)
        a2h = np.asarray(mat["gc_a2h"], dtype=float).reshape(-1)
        h2a = np.asarray(mat["gc_h2a"], dtype=float).reshape(-1)
        subject = str(mat["subject"]).lower()
        run_id = mat_path.name.removesuffix("_arousal_fullspectrum.mat")

        for band, label, lo, hi in BANDS:
            if band == "gamma":
                mask = (freqs >= lo) & (freqs <= hi)
            else:
                mask = (freqs >= lo) & (freqs < hi)
            if not np.any(mask):
                continue

            rows.append(
                {
                    "subject": subject,
                    "run_id": run_id,
                    "band": band,
                    "band_label": label,
                    "freq_low_hz": lo,
                    "freq_high_hz": hi,
                    "n_freq_bins": int(np.sum(mask)),
                    "A_to_H_gc": float(np.nanmean(a2h[mask])),
                    "H_to_A_gc": float(np.nanmean(h2a[mask])),
                }
            )

    return pd.DataFrame(rows)


def _subject_summary(run_band: pd.DataFrame) -> pd.DataFrame:
    return (
        run_band.groupby(["subject", "band", "band_label", "freq_low_hz", "freq_high_hz"], as_index=False)[
            ["A_to_H_gc", "H_to_A_gc"]
        ]
        .mean(numeric_only=True)
        .dropna(subset=["A_to_H_gc", "H_to_A_gc"], how="any")
    )


def _band_stats(subject_band: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for band, label, lo, hi in BANDS:
        part = subject_band[subject_band["band"] == band]
        a = part["A_to_H_gc"].to_numpy(dtype=float)
        h = part["H_to_A_gc"].to_numpy(dtype=float)
        ok = np.isfinite(a) & np.isfinite(h)
        a = a[ok]
        h = h[ok]
        n = len(a)
        if n >= 3:
            t_stat, p_val = ttest_rel(a, h, nan_policy="omit")
        else:
            t_stat, p_val = np.nan, np.nan
        rows.append(
            {
                "band": band,
                "band_label": label,
                "freq_low_hz": lo,
                "freq_high_hz": hi,
                "n_subjects": int(n),
                "A_to_H_mean": float(np.mean(a)) if n else np.nan,
                "H_to_A_mean": float(np.mean(h)) if n else np.nan,
                "A_to_H_sem": float(np.std(a, ddof=0) / np.sqrt(n)) if n else np.nan,
                "H_to_A_sem": float(np.std(h, ddof=0) / np.sqrt(n)) if n else np.nan,
                "paired_t": float(t_stat) if np.isfinite(t_stat) else np.nan,
                "paired_p": float(p_val) if np.isfinite(p_val) else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out["fdr_q05_sig"] = _fdr_bh(out["paired_p"].to_numpy(dtype=float), alpha=0.05)
    return out


def _plot(stats: pd.DataFrame, output_png: Path) -> None:
    x = np.arange(len(stats))
    width = 0.36
    a_mean = stats["A_to_H_mean"].to_numpy(dtype=float)
    h_mean = stats["H_to_A_mean"].to_numpy(dtype=float)
    a_sem = stats["A_to_H_sem"].to_numpy(dtype=float)
    h_sem = stats["H_to_A_sem"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(11.0, 5.8), dpi=220)
    ax.bar(x - width / 2, a_mean, width=width, yerr=a_sem, capsize=4, color="#c44e52", alpha=0.9, label="A→H")
    ax.bar(x + width / 2, h_mean, width=width, yerr=h_sem, capsize=4, color="#4c72b0", alpha=0.9, label="H→A")

    y_max = np.nanmax(np.concatenate([a_mean + a_sem, h_mean + h_sem]))
    if not np.isfinite(y_max) or y_max <= 0:
        y_max = 1.0
    y_step = y_max * 0.075
    for i, row in stats.reset_index(drop=True).iterrows():
        top = max(row["A_to_H_mean"] + row["A_to_H_sem"], row["H_to_A_mean"] + row["H_to_A_sem"])
        y = top + y_step
        tick = y_step * 0.18
        ax.plot([x[i] - width / 2, x[i] - width / 2, x[i] + width / 2, x[i] + width / 2], [y - tick, y, y, y - tick], color="black", lw=1.1)
        ax.text(
            x[i],
            y + y_step * 0.08,
            "*" if bool(row["fdr_q05_sig"]) else "n.s.",
            ha="center",
            va="bottom",
            fontsize=13,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(stats["band_label"].tolist(), fontsize=12)
    ax.set_ylabel("谱格兰杰因果值", fontsize=14)
    ax.tick_params(axis="y", labelsize=12)
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper right", fontsize=12)
    ax.set_ylim(0, y_max * 1.26)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or args.input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    run_band = _collect_rows(args.input_dir)
    subject_band = _subject_summary(run_band)
    stats = _band_stats(subject_band)

    run_csv = output_dir / "arousal_sgc_five_band_run_summary.csv"
    subject_csv = output_dir / "arousal_sgc_five_band_subject_summary.csv"
    stats_csv = output_dir / "arousal_sgc_five_band_stats.csv"
    stats_json = output_dir / "arousal_sgc_five_band_stats.json"
    output_png = output_dir / "arousal_sgc_direction_five_bands.png"

    run_band.to_csv(run_csv, index=False)
    subject_band.to_csv(subject_csv, index=False)
    stats.to_csv(stats_csv, index=False)
    _plot(stats, output_png)

    summary = {
        "bands": [
            {"band": band, "label": label, "range_hz": [lo, hi]}
            for band, label, lo, hi in BANDS
        ],
        "n_runs": int(run_band["run_id"].nunique()),
        "n_subjects": int(subject_band["subject"].nunique()),
        "run_summary_csv": str(run_csv),
        "subject_summary_csv": str(subject_csv),
        "stats_csv": str(stats_csv),
        "figure": str(output_png),
        "stats": stats.replace({np.nan: None}).to_dict(orient="records"),
    }
    with stats_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"saved {run_csv}")
    print(f"saved {subject_csv}")
    print(f"saved {stats_csv}")
    print(f"saved {stats_json}")
    print(f"saved {output_png}")


if __name__ == "__main__":
    main()
