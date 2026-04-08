from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualize spike batch outputs")
    p.add_argument("--result-dir", type=Path, required=True, help="Directory containing spike_batch_summary.csv and per-subject npz/csv files")
    p.add_argument("--top-k", type=int, default=6, help="How many sessions to show in detail")
    return p.parse_args()


def _safe_float(v: object) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def plot_summary(df: pd.DataFrame, out_dir: Path) -> None:
    ok = df[df["status"] == "ok"].copy()
    ok["session"] = ok["nwb_file"].apply(lambda s: Path(str(s)).stem)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    axes[0, 0].hist(ok["n_clean_trials"].dropna(), bins=20, color="#2E86AB", alpha=0.9)
    axes[0, 0].set_title("Distribution of Clean Trials")
    axes[0, 0].set_xlabel("n_clean_trials")
    axes[0, 0].set_ylabel("count")

    axes[0, 1].hist(ok["n_units"].dropna(), bins=20, color="#F18F01", alpha=0.9)
    axes[0, 1].set_title("Distribution of Units")
    axes[0, 1].set_xlabel("n_units")
    axes[0, 1].set_ylabel("count")

    axes[1, 0].scatter(ok["n_units"], ok["ifr_peak"], s=28, alpha=0.8, color="#C73E1D")
    axes[1, 0].set_title("IFR Peak vs Units")
    axes[1, 0].set_xlabel("n_units")
    axes[1, 0].set_ylabel("ifr_peak")

    axes[1, 1].scatter(ok["rho_median"], ok["p_lt_0_05_ratio"], s=28, alpha=0.8, color="#2A9D8F")
    axes[1, 1].set_title("Coupling Strength vs Significant-Ratio")
    axes[1, 1].set_xlabel("rho_median")
    axes[1, 1].set_ylabel("p_lt_0_05_ratio")

    fig.suptitle("Spike Batch Summary", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "spike_summary_overview.png", dpi=150)
    plt.close(fig)


def plot_top_sessions(df: pd.DataFrame, result_dir: Path, out_dir: Path, top_k: int) -> None:
    ok = df[df["status"] == "ok"].copy()
    ok = ok.sort_values("ifr_peak", ascending=False).head(top_k)

    for _, row in ok.iterrows():
        subject = str(row["subject"])
        npz_path = result_dir / f"{subject}_spike_ifr_psth.npz"
        if not npz_path.exists():
            continue

        data = np.load(npz_path)
        ifr = data["ifr"]
        ifr_times = data["ifr_times"]
        psth_neg = data["psth_negative"]
        psth_neu = data["psth_neutral"]
        psth_pos = data["psth_positive"]

        fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

        if ifr.size > 0:
            ifr_mean = np.nanmean(ifr, axis=0)
            ifr_lo = np.nanpercentile(ifr, 10, axis=0)
            ifr_hi = np.nanpercentile(ifr, 90, axis=0)
            axes[0].plot(ifr_times, ifr_mean, color="#2E86AB", lw=1.8, label="mean IFR")
            axes[0].fill_between(ifr_times, ifr_lo, ifr_hi, color="#2E86AB", alpha=0.2, label="10-90%")
        axes[0].axvline(0.0, color="black", lw=1.0, ls="--")
        axes[0].set_title(f"IFR Envelope: {subject}")
        axes[0].set_xlabel("time (s)")
        axes[0].set_ylabel("rate (a.u.)")
        axes[0].legend(loc="upper right", fontsize=8)

        axes[1].plot(ifr_times, psth_neg, label="negative", color="#D7263D", lw=1.4)
        axes[1].plot(ifr_times, psth_neu, label="neutral", color="#1B998B", lw=1.4)
        axes[1].plot(ifr_times, psth_pos, label="positive", color="#2E294E", lw=1.4)
        axes[1].axvline(0.0, color="black", lw=1.0, ls="--")
        axes[1].set_title(f"PSTH by Valence: {subject}")
        axes[1].set_xlabel("time (s)")
        axes[1].set_ylabel("rate (a.u.)")
        axes[1].legend(loc="upper right", fontsize=8)

        session_name = Path(str(row["nwb_file"])).stem
        fig.tight_layout()
        fig.savefig(out_dir / f"{subject}_{session_name}_ifr_psth.png", dpi=150)
        plt.close(fig)


def plot_subject_table(df: pd.DataFrame, out_dir: Path) -> None:
    ok = df[df["status"] == "ok"].copy()
    agg = (
        ok.groupby("subject", as_index=False)
        .agg(
            sessions=("nwb_file", "count"),
            clean_trials_median=("n_clean_trials", "median"),
            units_median=("n_units", "median"),
            ifr_peak_max=("ifr_peak", "max"),
            rho_median_mean=("rho_median", "mean"),
            sig_ratio_mean=("p_lt_0_05_ratio", "mean"),
        )
        .sort_values("ifr_peak_max", ascending=False)
    )
    agg.to_csv(out_dir / "spike_subject_aggregate.csv", index=False)


def main() -> None:
    args = parse_args()
    result_dir = args.result_dir
    summary_path = result_dir / "spike_batch_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary not found: {summary_path}")

    out_dir = result_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(summary_path)

    # Normalize numeric fields robustly for plotting.
    for c in ["n_clean_trials", "n_units", "ifr_peak", "rho_median", "p_lt_0_05_ratio"]:
        if c in df.columns:
            df[c] = df[c].map(_safe_float)

    plot_summary(df, out_dir)
    plot_top_sessions(df, result_dir, out_dir, top_k=args.top_k)
    plot_subject_table(df, out_dir)

    print("saved", out_dir)


if __name__ == "__main__":
    main()
