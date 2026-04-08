from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_cs41_49(out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    pattern = re.compile(r"sub-cs(\d+)_", re.I)

    coh_frames: list[pd.DataFrame] = []
    for path in out_dir.glob("*_AH_coherence.csv"):
        if path.name.startswith("._") or path.name.startswith("all_subjects_") or path.stat().st_size <= 100:
            continue
        matched = pattern.search(path.name)
        if not matched:
            continue
        code = int(matched.group(1))
        if not (41 <= code <= 49):
            continue
        frame = pd.read_csv(path, usecols=["subject", "band", "valence", "A_H_coherence"])
        frame["run_id"] = path.stem.replace("_AH_coherence", "")
        coh_frames.append(frame)

    sgc_frames: list[pd.DataFrame] = []
    for path in out_dir.glob("*_sGC.csv"):
        if path.name.startswith("._") or path.name.startswith("all_subjects_") or path.stat().st_size <= 100:
            continue
        matched = pattern.search(path.name)
        if not matched:
            continue
        code = int(matched.group(1))
        if not (41 <= code <= 49):
            continue
        frame = pd.read_csv(path, usecols=["subject", "band", "valence", "A_to_H_gc", "H_to_A_gc"])
        frame["run_id"] = path.stem.replace("_sGC", "")
        sgc_frames.append(frame)

    if not coh_frames or not sgc_frames:
        raise RuntimeError("No valid cs41-49 outputs found")

    return pd.concat(coh_frames, ignore_index=True), pd.concat(sgc_frames, ignore_index=True)


def main() -> None:
    out = Path("/Volumes/rmhyw/keles_ah_nwb_pipeline/results/connectivity_only")
    coh, sgc = load_cs41_49(out)

    coh = coh.copy()
    coh["band"] = coh["band"].astype(str).str.lower()
    sgc = sgc.copy()
    sgc["band"] = sgc["band"].astype(str).str.lower()

    band_order = ["theta", "beta"]
    band_center = {"theta": 6.0, "beta": 21.5}

    run_pivot = (
        coh.groupby(["run_id", "band"], as_index=False)["A_H_coherence"]
        .mean()
        .pivot(index="band", columns="run_id", values="A_H_coherence")
        .reindex(band_order)
    )

    sgc_valid = sgc[np.isfinite(sgc["A_to_H_gc"]) & np.isfinite(sgc["H_to_A_gc"])].copy()
    sgc_agg = (
        sgc_valid.groupby("band", as_index=False)[["A_to_H_gc", "H_to_A_gc"]]
        .agg(["mean", "sem"])
    )
    sgc_agg.columns = ["band", "a_mean", "a_sem", "h_mean", "h_sem"]
    sgc_agg = sgc_agg.set_index("band").reindex(band_order).reset_index()

    x = np.array([band_center[b] for b in band_order], dtype=float)
    a_mean = sgc_agg["a_mean"].to_numpy(dtype=float)
    a_sem = sgc_agg["a_sem"].to_numpy(dtype=float)
    h_mean = sgc_agg["h_mean"].to_numpy(dtype=float)
    h_sem = sgc_agg["h_sem"].to_numpy(dtype=float)

    fig = plt.figure(figsize=(12.5, 5.2), dpi=200)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.35, 1.0, 1.0], wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    im = ax1.imshow(run_pivot.values, aspect="auto", cmap="viridis", interpolation="nearest")
    ax1.set_title("A  Coherence", loc="left", fontsize=15, fontweight="bold")
    ax1.set_xlabel("Run")
    ax1.set_ylabel("Band")
    ax1.set_yticks([0, 1], labels=["theta (4–8 Hz)", "beta (13–30 Hz)"])
    ax1.set_xticks(np.arange(run_pivot.shape[1]))
    ax1.set_xticklabels(run_pivot.columns, rotation=65, ha="right", fontsize=7)
    cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label("A-H coherence")

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(x, a_mean, color="#4d4d4d", lw=2.2, label="neu")
    ax2.fill_between(x, a_mean - a_sem, a_mean + a_sem, color="#4d4d4d", alpha=0.18)
    ax2.set_title("B  Spectral Granger Causality\nA→H", loc="left", fontsize=15, fontweight="bold")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Granger index")
    ax2.set_xlim(2, 45)
    ax2.set_xticks([4, 8, 12, 28, 45])
    ax2.grid(alpha=0.25)
    ax2.legend(frameon=False, loc="upper right")

    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(x, h_mean, color="#4d4d4d", lw=2.2, label="neu")
    ax3.fill_between(x, h_mean - h_sem, h_mean + h_sem, color="#4d4d4d", alpha=0.18)
    ax3.set_title("H→A", fontsize=13, fontweight="bold")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_xlim(2, 45)
    ax3.set_xticks([4, 8, 12, 28, 45])
    ax3.grid(alpha=0.25)

    fig.suptitle(
        "Literature-style preview (cs41–49) — available data only: band-level + neutral only",
        fontsize=11,
        y=0.99,
    )

    out_png = out / "literature_style_preview_cs41_49.png"
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png)
    plt.close(fig)

    print(f"saved {out_png}")


if __name__ == "__main__":
    main()
