from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualize rating_c3 like/dislike IFR results")
    p.add_argument("--analysis-dir", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base = args.analysis_dir

    curves = pd.read_csv(base / "rating_c3_like45_dislike12_ifr_curves.csv")
    time_stats = pd.read_csv(base / "rating_c3_like45_dislike12_ifr_time_stats.csv")
    stats = pd.read_csv(base / "rating_c3_like45_dislike12_ifr_stats.csv")
    per_ch = pd.read_csv(base / "rating_c3_like45_dislike12_ifr_per_channel.csv")

    def significant_segments(t: np.ndarray, sig: np.ndarray) -> list[tuple[float, float]]:
        segs: list[tuple[float, float]] = []
        if len(t) == 0:
            return segs
        sig = np.asarray(sig, dtype=bool)
        starts = np.where(sig & np.r_[True, ~sig[:-1]])[0]
        ends = np.where(sig & np.r_[~sig[1:], True])[0]
        for s, e in zip(starts, ends, strict=True):
            segs.append((float(t[s]), float(t[e])))
        return segs

    # Figure 1: Time curves by region
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    panels = [
        ("overall", "Overall"),
        ("amygdala", "Amygdala"),
        ("hippocampus", "Hippocampus"),
    ]
    for ax, (key, title) in zip(axes, panels, strict=True):
        c = time_stats[time_stats["region"] == key].copy()
        t = c["time_s"].to_numpy(dtype=float)
        like_mean = c["like_mean_hz"].to_numpy(dtype=float)
        dislike_mean = c["dislike_mean_hz"].to_numpy(dtype=float)
        like_std = c["like_std_hz"].to_numpy(dtype=float)
        dislike_std = c["dislike_std_hz"].to_numpy(dtype=float)

        ax.plot(t, like_mean, lw=2, color="#c62828", label="Like")
        ax.plot(t, dislike_mean, lw=2, color="#1565c0", label="Dislike")

        p = c["p_fdr"].to_numpy(dtype=float)
        if np.all(~np.isfinite(p)):
            p = c["p_raw"].to_numpy(dtype=float)
        sig = np.isfinite(p) & (p < 0.05)

        # Draw significant intervals as horizontal bars near top of axis.
        y_min = float(np.nanmin(np.r_[like_mean - like_std, dislike_mean - dislike_std]))
        y_max = float(np.nanmax(np.r_[like_mean + like_std, dislike_mean + dislike_std]))
        y_bar = y_max - 0.04 * (y_max - y_min + 1e-12)
        for x0, x1 in significant_segments(t, sig):
            ax.plot([x0, x1], [y_bar, y_bar], color="black", lw=3, solid_capstyle="butt")

        ax.axvline(0, color="black", lw=1, ls="--")
        ax.set_ylabel("IFR (Hz)")
        n_sig = int(np.sum(sig))
        ax.set_title(f"{title} (sig bins={n_sig})")
        ax.legend(frameon=False, loc="upper right")
    axes[-1].set_xlabel("Time from event onset (s)")
    fig.suptitle("IFR Time Curves: Like vs Dislike", y=0.995)
    fig.tight_layout()
    out1 = base / "viz_ifr_timecurves_like_vs_dislike.png"
    fig.savefig(out1, dpi=170)
    plt.close(fig)

    # Figure 2: Region effect size bars
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(stats))
    y = stats["mean_diff_like_minus_dislike_hz"].to_numpy(dtype=float)
    colors = ["#455a64", "#8e24aa", "#00897b"]
    bars = ax.bar(x, y, color=colors[: len(x)], width=0.58)
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(stats["region"].tolist())
    ax.set_ylabel("Mean ΔIFR Like-Dislike (Hz)")
    ax.set_title("Region-Level Effect Size")

    for i, b in enumerate(bars):
        p = stats.iloc[i]["wilcoxon_p"]
        txt = f"p={p:.3f}" if np.isfinite(p) else "p=NA"
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), txt, ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    out2 = base / "viz_ifr_region_effect_like_minus_dislike.png"
    fig.savefig(out2, dpi=170)
    plt.close(fig)

    # Figure 3: Channel-level distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    reg_order = ["amygdala", "hippocampus", "other"]
    reg_color = {"amygdala": "#ab47bc", "hippocampus": "#26a69a", "other": "#90a4ae"}
    xpos = {r: i for i, r in enumerate(reg_order)}

    for r in reg_order:
        d = per_ch[per_ch["region"] == r]
        if len(d) == 0:
            continue
        xj = np.full(len(d), xpos[r], dtype=float) + (np.random.rand(len(d)) - 0.5) * 0.25
        y = d["delta_diff_like_minus_dislike_hz"].to_numpy(dtype=float)
        ax.scatter(xj, y, s=24, alpha=0.75, color=reg_color[r], label=r)

    ax.axhline(0, color="black", lw=1)
    ax.set_xticks([xpos[r] for r in reg_order])
    ax.set_xticklabels(reg_order)
    ax.set_ylabel("Per-channel ΔIFR Like-Dislike (Hz)")
    ax.set_title("Channel-Level Effect Distribution")
    handles, labels = ax.get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    ax.legend(uniq.values(), uniq.keys(), frameon=False)
    fig.tight_layout()
    out3 = base / "viz_ifr_channel_distribution_like_minus_dislike.png"
    fig.savefig(out3, dpi=170)
    plt.close(fig)

    print("saved", out1)
    print("saved", out2)
    print("saved", out3)


if __name__ == "__main__":
    main()
