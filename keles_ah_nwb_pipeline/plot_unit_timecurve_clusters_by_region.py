from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

from cluster_unit_timecurves import unit_trial_rate_matrix, zscore_by_baseline
from ah_pipeline.nwb_io import load_events


BASE = Path("/Volumes/rmhyw/keles_ah_nwb_pipeline")
OUT_DIR = BASE / "results/spike_region_batch_000623/timecurve_clusters"
UNIT_TABLE = OUT_DIR / "unit_timecurve_cluster_table.csv"
EVENT_CSV = BASE / "data/events_allsubjects_scenecut_placeholder.csv"

T_MIN = -0.5
T_MAX = 2.0
BIN_MS = 10.0
SMOOTH_MS = 50.0

FONT_PATHS = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
]


def chinese_font(size: float) -> font_manager.FontProperties:
    for path in FONT_PATHS:
        if path.exists():
            return font_manager.FontProperties(fname=str(path), size=size)
    return font_manager.FontProperties(size=size)


def region_from_text(text: str) -> str:
    t = str(text).lower()
    if "amyg" in t:
        return "杏仁核"
    if "hipp" in t or "hippocampus" in t or "hc" in t:
        return "海马"
    return "其他"


def unit_region(units: pd.DataFrame, unit_index: int) -> str:
    if unit_index < 0 or unit_index >= len(units):
        return "未知"
    elec = units.iloc[unit_index].get("electrodes")
    if not hasattr(elec, "get"):
        return "未知"
    locs = elec.get("location", pd.Series([], dtype=str)).astype(str).tolist()
    labels = elec.get("label", pd.Series([], dtype=str)).astype(str).tolist()
    tags = {region_from_text(x) for x in locs + labels}
    if "杏仁核" in tags:
        return "杏仁核"
    if "海马" in tags:
        return "海马"
    return "其他"


def sem(curves: np.ndarray) -> np.ndarray:
    if curves.shape[0] <= 1:
        return np.zeros(curves.shape[1])
    return np.std(curves, axis=0, ddof=1) / np.sqrt(curves.shape[0])


def plot_group(ax, df: pd.DataFrame, curves: np.ndarray, title: str) -> None:
    colors = {0: "#1f77b4", 1: "#d62728"}
    labels = {0: "Cluster 0", 1: "Cluster 1"}

    for c in [0, 1]:
        idx = df["cluster"].to_numpy() == c
        n = int(np.sum(idx))
        if n == 0:
            continue
        mean = np.mean(curves[idx], axis=0)
        se = sem(curves[idx])
        ax.plot(BIN_CENTERS, mean, color=colors[c], lw=2.2, label=f"{labels[c]} (n={n})")
        ax.fill_between(BIN_CENTERS, mean - se, mean + se, color=colors[c], alpha=0.18, linewidth=0)

    ax.axvline(0.0, color="k", lw=1.2, ls="--")
    ax.axhline(0.0, color="k", lw=0.8, ls=":")
    ax.set_title(title, fontproperties=chinese_font(16))
    ax.grid(True, alpha=0.15)
    ax.tick_params(labelsize=12)


bin_s = BIN_MS / 1000.0
BIN_EDGES = np.arange(T_MIN, T_MAX + bin_s, bin_s)
BIN_CENTERS = (BIN_EDGES[:-1] + BIN_EDGES[1:]) / 2.0
SMOOTH_SIGMA_BINS = (SMOOTH_MS / 1000.0) / bin_s
BASE_IDX = np.where((BIN_CENTERS >= T_MIN) & (BIN_CENTERS < 0.0))[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(UNIT_TABLE)
    events = load_events(EVENT_CSV)

    curves = np.zeros((len(df), len(BIN_CENTERS)), dtype=float)
    regions = ["未知"] * len(df)

    for nwb_file, rows in df.groupby("nwb_file", sort=False):
        nwb_path = BASE / str(nwb_file)
        subject = rows["subject"].iloc[0]
        onsets = events.loc[events["subject"] == subject, "onset"].astype(float).to_numpy()
        if len(onsets) == 0:
            raise RuntimeError(f"No events for {subject}")

        with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
            nwb = io.read()
            units = nwb.units.to_dataframe().reset_index(drop=True)

        for row_idx, row in rows.iterrows():
            unit_index = int(row["unit_index"])
            spike_times = np.asarray(units.iloc[unit_index]["spike_times"], dtype=float)
            mat = unit_trial_rate_matrix(
                spike_times=spike_times,
                onsets=onsets,
                bin_edges=BIN_EDGES,
                tmin=T_MIN,
                tmax=T_MAX,
                smooth_sigma_bins=SMOOTH_SIGMA_BINS,
            )
            curve = np.mean(mat, axis=0)
            curves[row_idx] = zscore_by_baseline(curve, BASE_IDX)
            regions[row_idx] = unit_region(units, unit_index)

    df["region"] = regions
    detail_out = OUT_DIR / "unit_timecurve_cluster_table_with_region.csv"
    df.to_csv(detail_out, index=False)

    counts = (
        df.groupby(["region", "cluster"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=["杏仁核", "海马", "其他", "未知"], fill_value=0)
    )
    counts["合计"] = counts.sum(axis=1)
    count_out = OUT_DIR / "unit_timecurve_cluster_region_counts.csv"
    counts.to_csv(count_out)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), sharey=True)
    panels = [
        ("全部", df.index.to_numpy()),
        ("杏仁核", df.index[df["region"] == "杏仁核"].to_numpy()),
        ("海马", df.index[df["region"] == "海马"].to_numpy()),
    ]
    for ax, (name, idx) in zip(axes, panels, strict=True):
        sub_df = df.iloc[idx].reset_index(drop=True)
        sub_curves = curves[idx]
        title = f"{name} (n={len(sub_df)}个单元)"
        plot_group(ax, sub_df, sub_curves, title)

    axes[0].set_ylabel("单元放电率（z，基线标准化）", fontproperties=chinese_font(14))
    for ax in axes:
        ax.set_xlabel("事件开始后的时间（秒）", fontproperties=chinese_font(14))
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(chinese_font(12))

    handles, labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.98, 0.98), frameon=False)
    for text in leg.get_texts():
        text.set_fontproperties(chinese_font(12))

    fig.subplots_adjust(left=0.08, right=0.83, bottom=0.18, top=0.82, wspace=0.18)
    fig_out = OUT_DIR / "unit_timecurve_cluster_prototypes_by_region_1x3_chinese.png"
    fig.savefig(fig_out, dpi=300)
    plt.close(fig)

    print("region_cluster_counts")
    print(counts.to_string())
    print(f"saved {detail_out}")
    print(f"saved {count_out}")
    print(f"saved {fig_out}")


if __name__ == "__main__":
    main()
