from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualize region-aware spike batch outputs")
    p.add_argument("--result-dir", type=Path, required=True, help="Directory containing spike_region_batch_summary.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    result_dir = args.result_dir
    summary_path = result_dir / "spike_region_batch_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)

    out_dir = result_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(summary_path)
    ok = df[df["status"] == "ok"].copy()

    for c in [
        "n_units_a",
        "n_units_h",
        "rho_aa_median",
        "rho_hh_median",
        "rho_ah_median",
        "rho_ha_median",
        "sig_aa_ratio",
        "sig_hh_ratio",
        "sig_ah_ratio",
        "sig_ha_ratio",
        "lag_ms_median",
        "n_clean_trials",
    ]:
        if c in ok.columns:
            ok[c] = pd.to_numeric(ok[c], errors="coerce")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    axes[0, 0].hist(ok["n_units_a"].dropna(), bins=16, alpha=0.7, label="A units", color="#D1495B")
    axes[0, 0].hist(ok["n_units_h"].dropna(), bins=16, alpha=0.7, label="H units", color="#00798C")
    axes[0, 0].set_title("Unit Count by Region")
    axes[0, 0].set_xlabel("units")
    axes[0, 0].set_ylabel("count")
    axes[0, 0].legend()

    axes[0, 1].hist(ok["lag_ms_median"].dropna(), bins=20, color="#30638E", alpha=0.9)
    axes[0, 1].axvline(0, color="black", ls="--", lw=1)
    axes[0, 1].set_title("A-H Median Lag (ms)")
    axes[0, 1].set_xlabel("lag_ms_median (positive: A leads)")
    axes[0, 1].set_ylabel("count")

    axes[1, 0].scatter(ok["rho_aa_median"], ok["rho_hh_median"], s=28, alpha=0.8, color="#8D6A9F")
    axes[1, 0].axhline(0, color="gray", lw=0.8)
    axes[1, 0].axvline(0, color="gray", lw=0.8)
    axes[1, 0].set_title("Within-region Coupling")
    axes[1, 0].set_xlabel("rho_aa_median")
    axes[1, 0].set_ylabel("rho_hh_median")

    axes[1, 1].scatter(ok["rho_ah_median"], ok["rho_ha_median"], s=28, alpha=0.8, color="#3E8914")
    axes[1, 1].axhline(0, color="gray", lw=0.8)
    axes[1, 1].axvline(0, color="gray", lw=0.8)
    axes[1, 1].set_title("Cross-region Coupling")
    axes[1, 1].set_xlabel("rho_ah_median")
    axes[1, 1].set_ylabel("rho_ha_median")

    fig.suptitle("Region-aware Spike Summary (A/H)", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "spike_region_summary_overview.png", dpi=150)
    plt.close(fig)

    agg = (
        ok.groupby("subject", as_index=False)
        .agg(
            sessions=("nwb_file", "count"),
            clean_trials_median=("n_clean_trials", "median"),
            units_a_median=("n_units_a", "median"),
            units_h_median=("n_units_h", "median"),
            rho_aa_median=("rho_aa_median", "median"),
            rho_hh_median=("rho_hh_median", "median"),
            rho_ah_median=("rho_ah_median", "median"),
            rho_ha_median=("rho_ha_median", "median"),
            lag_ms_median=("lag_ms_median", "median"),
        )
        .sort_values("sessions", ascending=False)
    )
    agg.to_csv(out_dir / "spike_region_subject_aggregate.csv", index=False)

    print("saved", out_dir)


if __name__ == "__main__":
    main()
