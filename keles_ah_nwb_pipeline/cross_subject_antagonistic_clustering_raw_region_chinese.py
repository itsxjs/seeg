from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans

from cross_subject_antagonistic_clustering_raw import (
    BIN_CENTERS,
    BIN_SIZE,
    SIG_START,
    SUBJECTS,
    contiguous_sig_windows,
    fdr_bh,
    load_data,
    trimmed_mean_sem,
)


RESULT_DIR = Path("/Volumes/rmhyw/keles_ah_nwb_pipeline/results")
FONT_PATHS = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
]

ELECTRODE_XML = {
    "sub001_Shan": Path(
        "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/"
        "ZE-EPI-VE-20241202-1330/electrodes.xml"
    ),
    "sub008_Jiang": Path("/Volumes/rmhyw/姜芳丽spike_rate/electrodes.xml"),
}


def chinese_font() -> font_manager.FontProperties:
    for path in FONT_PATHS:
        if path.exists():
            return font_manager.FontProperties(fname=str(path))
    return font_manager.FontProperties()


FONT = chinese_font()


def font_with_size(size: float) -> font_manager.FontProperties:
    prop = FONT.copy()
    prop.set_size(size)
    return prop


def set_chinese_style() -> None:
    plt.rcParams.update(
        {
            "axes.titlesize": 30,
            "axes.labelsize": 27,
            "xtick.labelsize": 24,
            "ytick.labelsize": 24,
            "legend.fontsize": 25,
            "figure.titlesize": 34,
            "axes.unicode_minus": False,
        }
    )


def normalize_region(text: str) -> str:
    if "杏仁" in text:
        return "杏仁核"
    if "海马" in text:
        return "海马"
    return "其他"


def load_unit_regions(xml_path: Path, n_units: int) -> list[str]:
    """Map spike_Tps cell order to the microelectrode order in electrodes.xml."""
    root = ET.parse(xml_path).getroot()
    regions: list[str] = []
    for config in root.iter("ElectrodeConfiguration"):
        config_name = config.attrib.get("name", "")
        for site in config:
            if site.tag != "MicroElectrodeSite":
                continue
            area = site.attrib.get("implantArea") or config_name
            regions.append(normalize_region(area))

    if len(regions) < n_units:
        regions.extend(["未知"] * (n_units - len(regions)))
    return regions[:n_units]


def compute_sig_windows(like_curves: np.ndarray, dislike_curves: np.ndarray) -> list[tuple[float, float]]:
    if like_curves.shape[0] < 2:
        return []
    _, pvals = stats.ttest_rel(like_curves, dislike_curves, axis=0, nan_policy="omit")
    sig_mask = fdr_bh(pvals, alpha=0.05)
    sig_mask = sig_mask & (BIN_CENTERS >= SIG_START)
    return contiguous_sig_windows(sig_mask, BIN_CENTERS, BIN_SIZE, min_bins=2)


def plot_panel(
    ax,
    like_curves: np.ndarray,
    dislike_curves: np.ndarray,
    title: str,
    title_size: float = 30,
) -> None:
    n_units = like_curves.shape[0]
    if n_units == 0:
        ax.set_title(f"{title}（n=0）", fontproperties=font_with_size(title_size))
        ax.axvline(0, color="black", linestyle="--", linewidth=1.5)
        ax.grid(True, alpha=0.15)
        return

    like_mean, like_sem = trimmed_mean_sem(like_curves, trim_frac=0.2)
    dislike_mean, dislike_sem = trimmed_mean_sem(dislike_curves, trim_frac=0.2)

    ax.plot(BIN_CENTERS, like_mean, color="red", linewidth=2.5, label="喜欢")
    ax.fill_between(
        BIN_CENTERS,
        like_mean - like_sem,
        like_mean + like_sem,
        color="red",
        alpha=0.12,
        linewidth=0,
    )
    ax.plot(BIN_CENTERS, dislike_mean, color="blue", linewidth=2.5, label="不喜欢")
    ax.fill_between(
        BIN_CENTERS,
        dislike_mean - dislike_sem,
        dislike_mean + dislike_sem,
        color="blue",
        alpha=0.12,
        linewidth=0,
    )

    for i, (t0, t1) in enumerate(compute_sig_windows(like_curves, dislike_curves)):
        label = "FDR<0.05" if i == 0 else None
        ax.axvspan(t0, t1, color="gold", alpha=0.16, label=label)

    ax.axvline(0, color="black", linestyle="--", linewidth=1.5)
    ax.set_title(f"{title}（n={n_units}个单元）", fontproperties=font_with_size(title_size))
    ax.grid(True, alpha=0.15)


def add_figure_legend(fig) -> None:
    handles = [
        Line2D([0], [0], color="red", lw=3.5, label="喜欢"),
        Line2D([0], [0], color="blue", lw=3.5, label="不喜欢"),
        Patch(facecolor="gold", edgecolor="gold", alpha=0.16, label="FDR<0.05"),
    ]
    leg = fig.legend(
        handles=handles,
        loc="upper right",
        bbox_to_anchor=(0.98, 0.98),
        frameon=False,
        prop=font_with_size(25),
    )
    for text in leg.get_texts():
        text.set_fontproperties(font_with_size(25))


def add_like_dislike_legend(fig) -> None:
    handles = [
        Line2D([0], [0], color="red", lw=2.5, label="喜欢"),
        Line2D([0], [0], color="blue", lw=2.5, label="不喜欢"),
    ]
    leg = fig.legend(
        handles=handles,
        loc="upper right",
        bbox_to_anchor=(0.95, 0.98),
        frameon=False,
        prop=font_with_size(16),
    )
    for text in leg.get_texts():
        text.set_fontproperties(font_with_size(16))


def apply_axis_labels(fig, axes, title: str) -> None:
    axes_arr = np.asarray(axes)
    if axes_arr.ndim == 1:
        bottom_axes = axes_arr
        left_axes = [axes_arr[0]]
    else:
        bottom_axes = axes_arr[-1, :]
        left_axes = axes_arr[:, 0]

    for ax in np.ravel(axes_arr):
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(font_with_size(24))
    for ax in bottom_axes:
        ax.set_xlabel("刺激开始后的时间（秒）", fontproperties=font_with_size(27))
    for ax in left_axes:
        ax.set_ylabel("基线校正放电率（Hz）", fontproperties=font_with_size(27))
    if title:
        fig.suptitle(title, fontproperties=font_with_size(34), y=0.97)

    if axes_arr.ndim == 1:
        fig.subplots_adjust(left=0.08, right=0.98, bottom=0.14, top=0.66, wspace=0.12)
    else:
        fig.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.78, wspace=0.12, hspace=0.42)


def apply_ppt_axis_labels(axes) -> None:
    axes_arr = np.asarray(axes)
    for ax in np.ravel(axes_arr):
        ax.tick_params(axis="both", labelsize=12)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(font_with_size(12))
    for ax in axes_arr[-1, :]:
        ax.set_xlabel("刺激开始后的时间（秒）", fontproperties=font_with_size(14))
    for ax in axes_arr[:, 0]:
        ax.set_ylabel("基线校正放电率（Hz）", fontproperties=font_with_size(14))


def analyze() -> None:
    set_chinese_style()

    all_features = []
    all_raw_like = []
    all_raw_dislike = []
    meta_rows: list[dict[str, object]] = []

    for sub, config in SUBJECTS.items():
        feat, raw_l, raw_d, ids = load_data(sub, config)
        if feat.size == 0:
            continue
        regions = load_unit_regions(ELECTRODE_XML[sub], len(ids))
        all_features.append(feat)
        all_raw_like.append(raw_l)
        all_raw_dislike.append(raw_d)
        for local_idx, unit_id in enumerate(ids):
            meta_rows.append(
                {
                    "subject": sub,
                    "local_unit_index": int(local_idx),
                    "unit_id": unit_id,
                    "region": regions[local_idx],
                }
            )

    X = np.vstack(all_features)
    y_like = np.vstack(all_raw_like)
    y_dislike = np.vstack(all_raw_dislike)

    clusters = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(X)
    meta = pd.DataFrame(meta_rows)
    meta["cluster"] = clusters.astype(int)

    count_table = (
        meta[meta["region"].isin(["杏仁核", "海马"])]
        .groupby(["cluster", "region"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=[0, 1], columns=["杏仁核", "海马"], fill_value=0)
    )
    count_table.index.name = "cluster"

    detail_out = RESULT_DIR / "antagonistic_clusters_region_unit_table.csv"
    count_out = RESULT_DIR / "antagonistic_clusters_region_unit_counts.csv"
    meta.to_csv(detail_out, index=False)
    count_table.to_csv(count_out)

    fig_all, axes_all = plt.subplots(1, 2, figsize=(18, 7), sharey=True)
    for c in [0, 1]:
        idx = clusters == c
        plot_panel(axes_all[c], y_like[idx], y_dislike[idx], f"Cluster {c}")
    apply_axis_labels(
        fig_all,
        axes_all,
        "",
    )
    add_figure_legend(fig_all)
    chinese_copy = RESULT_DIR / "antagonistic_clusters_raw_ifr_with_robust_sem_sig_chinese.png"
    fig_all.savefig(chinese_copy, dpi=300)
    plt.close(fig_all)

    fig_all_vertical, axes_all_vertical = plt.subplots(2, 1, figsize=(9, 12), sharex=True, sharey=True)
    for c in [0, 1]:
        idx = clusters == c
        plot_panel(axes_all_vertical[c], y_like[idx], y_dislike[idx], f"Cluster {c}")
    apply_axis_labels(
        fig_all_vertical,
        axes_all_vertical,
        "",
    )
    fig_all_vertical.subplots_adjust(left=0.18, right=0.96, bottom=0.09, top=0.94, hspace=0.34)
    vertical_copy = RESULT_DIR / "antagonistic_clusters_raw_ifr_with_robust_sem_sig_chinese_vertical_no_legend.png"
    fig_all_vertical.savefig(vertical_copy, dpi=300)
    plt.close(fig_all_vertical)

    fig_ppt, axes_ppt = plt.subplots(2, 3, figsize=(16, 7.5), sharex=True)
    ppt_columns = [
        ("", None),
        (" - 杏仁核", "杏仁核"),
        (" - 海马", "海马"),
    ]
    for row, c in enumerate([0, 1]):
        for col, (suffix, region) in enumerate(ppt_columns):
            if region is None:
                idx = clusters == c
            else:
                idx = (clusters == c) & (meta["region"].to_numpy() == region)
            plot_panel(
                axes_ppt[row, col],
                y_like[idx],
                y_dislike[idx],
                f"Cluster {c}{suffix}",
                title_size=15,
            )
    apply_ppt_axis_labels(axes_ppt)
    add_like_dislike_legend(fig_ppt)
    fig_ppt.subplots_adjust(left=0.08, right=0.88, bottom=0.11, top=0.84, wspace=0.18, hspace=0.38)
    ppt_copy = RESULT_DIR / "antagonistic_clusters_raw_ifr_ppt_style_2x3_chinese.png"
    fig_ppt.savefig(ppt_copy, dpi=300)
    plt.close(fig_ppt)

    fig_split, axes_split = plt.subplots(2, 2, figsize=(18, 12), sharex=True, sharey=True)
    region_names = ["杏仁核", "海马"]
    for row, c in enumerate([0, 1]):
        for col, region in enumerate(region_names):
            idx = (clusters == c) & (meta["region"].to_numpy() == region)
            plot_panel(axes_split[row, col], y_like[idx], y_dislike[idx], f"Cluster {c} - {region}")
    apply_axis_labels(
        fig_split,
        axes_split,
        "",
    )
    add_figure_legend(fig_split)
    split_copy = RESULT_DIR / "antagonistic_clusters_raw_ifr_region_2x2_chinese.png"
    fig_split.savefig(split_copy, dpi=300)
    plt.close(fig_split)

    print("Cluster-region counts:")
    print(count_table.to_string())
    other_counts = meta[~meta["region"].isin(["杏仁核", "海马"])].groupby(["cluster", "region"]).size()
    if len(other_counts):
        print("\nNon-target regions also present:")
        print(other_counts.to_string())
    print(f"\nSaved unit table: {detail_out}")
    print(f"Saved count table: {count_out}")
    print(f"Saved Chinese copy: {chinese_copy}")
    print(f"Saved vertical no-legend copy: {vertical_copy}")
    print(f"Saved PPT-style 2x3 copy: {ppt_copy}")
    print(f"Saved region 2x2 copy: {split_copy}")


if __name__ == "__main__":
    analyze()
