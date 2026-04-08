from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.image import imread
from scipy.io import loadmat


CONDS = ["positive", "neutral", "negative"]
COND_COLORS = {
    "positive": "#1f77b4",  # blue
    "neutral": "#4d4d4d",   # gray
    "negative": "#d62728",  # red
}


def _mean_sem(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.nanmean(arr, axis=0)
    valid_counts = np.sum(np.isfinite(arr), axis=0)
    std = np.nanstd(arr, axis=0, ddof=0)
    sem = np.full_like(std, np.nan, dtype=float)
    mask = valid_counts > 0
    sem[mask] = std[mask] / np.sqrt(valid_counts[mask])
    sem[valid_counts == 0] = np.nan
    return mean, sem


def _collect_sgc_subject_mats(scene_dir: Path) -> list[Path]:
    return sorted(scene_dir.glob("*_sGC_Amy_Hip_Scene_Results.mat"))


def _load_subject_sgc(mat_path: Path) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    mat = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
    res = mat["res"]
    if not hasattr(res, "sgc") or not hasattr(res.sgc, "Amy_Hip"):
        raise ValueError(f"Incompatible file (missing res.sgc.Amy_Hip): {mat_path}")
    freq = np.asarray(res.freq_vec).astype(float).ravel()

    a_to_h: dict[str, np.ndarray] = {}
    h_to_a: dict[str, np.ndarray] = {}

    amy_hip = res.sgc.Amy_Hip
    for cond in CONDS:
        if not hasattr(amy_hip, cond):
            raise ValueError(f"Condition {cond} missing in {mat_path}")
        node = getattr(amy_hip, cond)
        a_to_h[cond] = np.asarray(node.A_to_H).astype(float).ravel()
        h_to_a[cond] = np.asarray(node.H_to_A).astype(float).ravel()

    return freq, a_to_h, h_to_a


def _stack_by_condition(items: Iterable[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    out: dict[str, list[np.ndarray]] = {c: [] for c in CONDS}
    for obj in items:
        for c in CONDS:
            out[c].append(obj[c])
    return {c: np.vstack(out[c]) for c in CONDS if out[c]}


def plot_scene_connectivity_figure(
    coh_group_png: Path,
    scene_dir: Path,
    output_png: Path,
) -> None:
    sgc_mats = _collect_sgc_subject_mats(scene_dir)
    if not sgc_mats:
        raise FileNotFoundError(f"No *_sGC_Amy_Hip_Scene_Results.mat found in {scene_dir}")

    freqs: np.ndarray | None = None
    a2h_list: list[dict[str, np.ndarray]] = []
    h2a_list: list[dict[str, np.ndarray]] = []

    used_subjects: list[str] = []
    skipped_subjects: list[str] = []

    for mat_path in sgc_mats:
        try:
            freq, a_to_h, h_to_a = _load_subject_sgc(mat_path)
        except Exception:
            skipped_subjects.append(mat_path.name)
            continue
        if freqs is None:
            freqs = freq
        a2h_list.append(a_to_h)
        h2a_list.append(h_to_a)
        used_subjects.append(mat_path.name)

    if freqs is None or not a2h_list or not h2a_list:
        raise RuntimeError(f"No valid sGC files found in {scene_dir}")
    a2h_stack = _stack_by_condition(a2h_list)
    h2a_stack = _stack_by_condition(h2a_list)

    fig = plt.figure(figsize=(13.5, 5.2), dpi=200)
    gs = GridSpec(1, 3, width_ratios=[1.05, 1.0, 1.0], wspace=0.30, figure=fig)

    ax0 = fig.add_subplot(gs[0, 0])
    if coh_group_png.exists():
        ax0.imshow(imread(coh_group_png))
        ax0.set_axis_off()
        ax0.set_title("A  Coherence (A-H, group)", loc="left", fontsize=15, fontweight="bold")
    else:
        ax0.text(0.5, 0.5, f"Missing:\n{coh_group_png}", ha="center", va="center")
        ax0.set_axis_off()

    ax1 = fig.add_subplot(gs[0, 1])
    for cond in CONDS:
        y = a2h_stack.get(cond)
        if y is None:
            continue
        mean, sem = _mean_sem(y)
        color = COND_COLORS[cond]
        ax1.plot(freqs, mean, color=color, lw=2.0, label=cond[:3])
        ax1.fill_between(freqs, mean - sem, mean + sem, color=color, alpha=0.18, linewidth=0)
    ax1.set_title("B  Spectral Granger Causality\nA→H", loc="left", fontsize=15, fontweight="bold")
    ax1.set_xlabel("Frequency (Hz)")
    ax1.set_ylabel("Granger index")
    ax1.set_xlim(2, 45)
    ax1.grid(alpha=0.2)

    ax2 = fig.add_subplot(gs[0, 2])
    for cond in CONDS:
        y = h2a_stack.get(cond)
        if y is None:
            continue
        mean, sem = _mean_sem(y)
        color = COND_COLORS[cond]
        ax2.plot(freqs, mean, color=color, lw=2.0, label=cond[:3])
        ax2.fill_between(freqs, mean - sem, mean + sem, color=color, alpha=0.18, linewidth=0)
    ax2.set_title("H→A", fontsize=14, fontweight="bold")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.2)
    ax2.legend(frameon=False, loc="upper right")

    subtitle = f"sGC subjects used: {len(used_subjects)}"
    if skipped_subjects:
        subtitle += f" | skipped: {len(skipped_subjects)}"
    fig.suptitle(subtitle, y=0.99, fontsize=10)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    out_png = project_root / "results" / "connectivity_only" / "scene_style_connectivity_AH.png"

    plot_scene_connectivity_figure(
        coh_group_png=Path("/Users/defanive/Desktop/Diploma/coh_pipeline/coherence_out/GROUP_A_H_all_coh.png"),
        scene_dir=Path("/Users/defanive/Desktop/Diploma/seeg分析脚本scene"),
        output_png=out_png,
    )
    print(f"saved {out_png}")
