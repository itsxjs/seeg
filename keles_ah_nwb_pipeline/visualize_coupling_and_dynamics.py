"""
Visualize coupling strength and temporal dynamics.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualize coupling and dynamics")
    p.add_argument("--analysis-dir", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base = args.analysis_dir

    coupling = pd.read_csv(base / "coupling_strength.csv")
    dynamics = pd.read_csv(base / "temporal_dynamics.csv")

    # Figure 1: Coupling strength comparison
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Coupling data for plotting
    coupling_pivot = coupling.groupby(["coupling_type", "phase"])["mean_corr"].mean().reset_index()
    
    ax = axes[0]
    for ct in ["intra_region", "inter_region"]:
        data = coupling_pivot[coupling_pivot["coupling_type"] == ct]
        like_val = data[data["phase"] == "like"]["mean_corr"].values
        dislike_val = data[data["phase"] == "dislike"]["mean_corr"].values
        
        like_val = like_val[0] if len(like_val) > 0 else 0
        dislike_val = dislike_val[0] if len(dislike_val) > 0 else 0
        
        x_pos = 0 if ct == "intra_region" else 1
        ax.bar(x_pos - 0.2, like_val, width=0.4, label="Like" if x_pos == 0 else "", color="#c62828")
        ax.bar(x_pos + 0.2, dislike_val, width=0.4, label="Dislike" if x_pos == 0 else "", color="#1565c0")
    
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Intra-region", "Inter-region"])
    ax.set_ylabel("Mean Pearson Correlation")
    ax.set_title("Coupling Strength: Like vs Dislike")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    
    # Coupling by region
    ax = axes[1]
    coupling_by_region = coupling.groupby(["region", "phase"])["mean_corr"].mean().reset_index()
    regions = coupling_by_region["region"].unique()
    x_pos = np.arange(len(regions))
    width = 0.35
    
    for i, region in enumerate(regions):
        region_data = coupling_by_region[coupling_by_region["region"] == region]
        like_val = region_data[region_data["phase"] == "like"]["mean_corr"].values
        dislike_val = region_data[region_data["phase"] == "dislike"]["mean_corr"].values
        
        like_val = like_val[0] if len(like_val) > 0 else 0
        dislike_val = dislike_val[0] if len(dislike_val) > 0 else 0
        
        ax.bar(i - width/2, like_val, width=width, color="#c62828", alpha=0.8)
        ax.bar(i + width/2, dislike_val, width=width, color="#1565c0", alpha=0.8)
    
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(regions, rotation=15, ha="right")
    ax.set_ylabel("Mean Pearson Correlation")
    ax.set_title("Coupling by Region")
    ax.grid(axis="y", alpha=0.3)
    
    fig.tight_layout()
    out1 = base / "viz_coupling_strength.png"
    fig.savefig(out1, dpi=170)
    plt.close(fig)
    print(f"saved {out1}")

    # Figure 2: Temporal dynamics - response slope
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Response slope by region and phase
    dyn_slope = dynamics.groupby(["region", "phase"])["response_slope_hz_per_s"].mean().reset_index()
    
    ax = axes[0]
    regions_list = ["amygdala", "hippocampus"]
    x_pos = np.arange(len(regions_list))
    width = 0.35
    
    for i, region in enumerate(regions_list):
        region_data = dyn_slope[dyn_slope["region"] == region]
        like_val = region_data[region_data["phase"] == "like"]["response_slope_hz_per_s"].values
        dislike_val = region_data[region_data["phase"] == "dislike"]["response_slope_hz_per_s"].values
        
        like_val = like_val[0] if len(like_val) > 0 else 0
        dislike_val = dislike_val[0] if len(dislike_val) > 0 else 0
        
        ax.bar(i - width/2, like_val, width=width, color="#c62828", alpha=0.8, label="Like" if i == 0 else "")
        ax.bar(i + width/2, dislike_val, width=width, color="#1565c0", alpha=0.8, label="Dislike" if i == 0 else "")
    
    ax.axhline(0, color="black", lw=1, linestyle="--")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(regions_list)
    ax.set_ylabel("Response Slope (Hz/s)")
    ax.set_title("Response Slope: Like vs Dislike")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    
    # Early vs Late response difference
    dyn_elate = dynamics.groupby(["region", "phase"])["early_late_diff_hz"].mean().reset_index()
    
    ax = axes[1]
    for i, region in enumerate(regions_list):
        region_data = dyn_elate[dyn_elate["region"] == region]
        like_val = region_data[region_data["phase"] == "like"]["early_late_diff_hz"].values
        dislike_val = region_data[region_data["phase"] == "dislike"]["early_late_diff_hz"].values
        
        like_val = like_val[0] if len(like_val) > 0 else 0
        dislike_val = dislike_val[0] if len(dislike_val) > 0 else 0
        
        ax.bar(i - width/2, like_val, width=width, color="#c62828", alpha=0.8)
        ax.bar(i + width/2, dislike_val, width=width, color="#1565c0", alpha=0.8)
    
    ax.axhline(0, color="black", lw=1, linestyle="--")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(regions_list)
    ax.set_ylabel("Late - Early Mean IFR (Hz)")
    ax.set_title("Response Acceleration: Late vs Early")
    ax.grid(axis="y", alpha=0.3)
    
    fig.tight_layout()
    out2 = base / "viz_temporal_dynamics.png"
    fig.savefig(out2, dpi=170)
    plt.close(fig)
    print(f"saved {out2}")

    # Figure 3: Per-channel response slope distribution
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    for phase_idx, (ax, phase_name) in enumerate([(axes[0], "like"), (axes[1], "dislike")]):
        phase_data = dynamics[dynamics["phase"] == phase_name]
        
        amyg_slopes = phase_data[phase_data["region"] == "amygdala"]["response_slope_hz_per_s"].values
        hipp_slopes = phase_data[phase_data["region"] == "hippocampus"]["response_slope_hz_per_s"].values
        
        bp = ax.boxplot([amyg_slopes, hipp_slopes], labels=["Amygdala", "Hippocampus"],
                        patch_artist=True, widths=0.6)
        
        # Color boxes
        colors = ["#ab47bc", "#26a69a"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.axhline(0, color="black", lw=1, linestyle="--", alpha=0.5)
        ax.set_ylabel("Response Slope (Hz/s)")
        ax.set_title(f"Response Slope Distribution ({phase_name.capitalize()})")
        ax.grid(axis="y", alpha=0.3)
    
    fig.tight_layout()
    out3 = base / "viz_temporal_dynamics_distribution.png"
    fig.savefig(out3, dpi=170)
    plt.close(fig)
    print(f"saved {out3}")

    # Print summary
    print("\n=== Coupling Summary ===")
    print(coupling.groupby(["coupling_type", "phase"])[["mean_corr"]].mean())
    print("\n=== Temporal Dynamics Summary ===")
    print(dynamics.groupby(["region", "phase"])[["response_slope_hz_per_s", "early_late_diff_hz"]].mean())


if __name__ == "__main__":
    main()
