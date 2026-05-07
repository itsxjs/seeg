from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "Heiti TC",
    "Songti SC",
    "PingFang SC",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 14
plt.rcParams["axes.labelsize"] = 15
plt.rcParams["xtick.labelsize"] = 13
plt.rcParams["ytick.labelsize"] = 13
plt.rcParams["legend.fontsize"] = 12


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

    def add_panel_label(ax, label: str) -> None:
        ax.text(
            -0.06,
            1.04,
            label,
            transform=ax.transAxes,
            fontsize=20,
            fontweight="bold",
            ha="left",
            va="bottom",
            fontfamily="DejaVu Serif",
            clip_on=False,
        )

    axes[0, 0].hist(ok["n_units_a"].dropna(), bins=16, alpha=0.7, label="杏仁核单元", color="#D1495B")
    axes[0, 0].hist(ok["n_units_h"].dropna(), bins=16, alpha=0.7, label="海马单元", color="#00798C")
    axes[0, 0].set_xlabel("单元数量")
    axes[0, 0].set_ylabel("计数")
    axes[0, 0].legend()

    axes[0, 1].hist(ok["lag_ms_median"].dropna(), bins=20, color="#30638E", alpha=0.9)
    axes[0, 1].axvline(0, color="black", ls="--", lw=1)
    axes[0, 1].set_xlabel("A-H中位时滞 (ms；正值表示A领先)")
    axes[0, 1].set_ylabel("计数")

    axes[1, 0].scatter(ok["rho_aa_median"], ok["rho_hh_median"], s=28, alpha=0.8, color="#8D6A9F")
    axes[1, 0].axhline(0, color="gray", lw=0.8)
    axes[1, 0].axvline(0, color="gray", lw=0.8)
    axes[1, 0].set_xlabel("杏仁核脑区内IFR-HG耦合中位数")
    axes[1, 0].set_ylabel("海马脑区内IFR-HG耦合中位数")

    axes[1, 1].scatter(ok["rho_ah_median"], ok["rho_ha_median"], s=28, alpha=0.8, color="#3E8914")
    axes[1, 1].axhline(0, color="gray", lw=0.8)
    axes[1, 1].axvline(0, color="gray", lw=0.8)
    axes[1, 1].set_xlabel("杏仁核IFR-海马HG耦合中位数")
    axes[1, 1].set_ylabel("海马IFR-杏仁核HG耦合中位数")

    for label, ax in zip(("a", "b", "c", "d"), axes.ravel()):
        add_panel_label(ax, label)

    fig.tight_layout()
    fig.savefig(out_dir / "spike_region_summary_overview.png", dpi=150)
    fig.savefig(out_dir / "spike_region_summary_overview_publication_cn.png", dpi=220, bbox_inches="tight")
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
