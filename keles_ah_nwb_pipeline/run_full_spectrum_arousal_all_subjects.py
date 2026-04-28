from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import savemat

from ah_pipeline.config import PipelineConfig
from ah_pipeline.nwb_io import iter_nwb_files, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from run_full_spectrum_connectivity_one_subject import compute_full_spectral_gc, compute_sliding_coherence_full


def _pick_region_pairs(channel_names: list[str], regions: list[str]) -> tuple[list[tuple[int, int, str]], list[int], list[int]]:
    amyg = [(idx, name) for idx, (name, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "amygdala"]
    hipp = [(idx, name) for idx, (name, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "hippocampus"]

    pairs: list[tuple[int, int, str]] = []
    for idx_a, name_a in amyg:
        for idx_h, name_h in hipp:
            pairs.append((idx_a, idx_h, f"{name_a}__{name_h}"))

    return pairs, [idx for idx, _ in amyg], [idx for idx, _ in hipp]


def _build_arousal_events(arousal_csv: Path, subject: str) -> pd.DataFrame:
    arousal_df = pd.read_csv(arousal_csv)
    required = {"center_sec", "start_sec", "end_sec"}
    missing = required - set(arousal_df.columns)
    if missing:
        raise ValueError(f"Missing columns in {arousal_csv}: {missing}")

    n_rows = len(arousal_df)
    out = pd.DataFrame(
        {
            "subject": [subject.lower()] * n_rows,
            "onset": arousal_df["center_sec"].astype(float).to_list(),
            "valence": ["neutral"] * n_rows,
            "event_type": ["ai_arousal_segment"] * n_rows,
        }
    )
    return out


def _plot_group_full_spectrum(
    out_dir: Path,
    freqs_coh: np.ndarray,
    time_coh: np.ndarray,
    coh_stack: np.ndarray,
    freqs_gc: np.ndarray,
    gc_a_stack: np.ndarray,
    gc_h_stack: np.ndarray,
    used_files: list[str],
) -> dict[str, str]:
    group_coh = np.nanmean(coh_stack, axis=0)
    group_gc_a = np.nanmean(gc_a_stack, axis=0)
    group_gc_h = np.nanmean(gc_h_stack, axis=0)
    gc_a_sem = np.nanstd(gc_a_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(gc_a_stack), axis=0), 1))
    gc_h_sem = np.nanstd(gc_h_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(gc_h_stack), axis=0), 1))

    pvals = np.full(len(freqs_gc), np.nan, dtype=float)
    for fi in range(len(freqs_gc)):
        a = gc_a_stack[:, fi]
        h = gc_h_stack[:, fi]
        ok = np.isfinite(a) & np.isfinite(h)
        if np.sum(ok) < 3:
            continue
        from scipy.stats import ttest_rel

        _, pvals[fi] = ttest_rel(a[ok], h[ok], nan_policy="omit")

    extent = [float(time_coh.min()), float(time_coh.max()), float(freqs_coh.min()), float(freqs_coh.max())]
    sig_mask = np.isfinite(pvals) & (pvals < 0.05)
    sig_spans = []
    if np.any(sig_mask):
        start = None
        for i, val in enumerate(sig_mask):
            if val and start is None:
                start = i
            if (not val or i == len(sig_mask) - 1) and start is not None:
                end = i if val and i == len(sig_mask) - 1 else i - 1
                sig_spans.append((float(freqs_gc[start]), float(freqs_gc[end])))
                start = None

    coh_png = out_dir / "group_fullspectrum_arousal_coherence.png"
    sgc_png = out_dir / "group_fullspectrum_arousal_sgc.png"
    combo_png = out_dir / "group_fullspectrum_arousal_literature_style.png"
    sig_png = out_dir / "group_fullspectrum_arousal_sgc_significance.png"

    fig1, ax1 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    im = ax1.imshow(group_coh, aspect="auto", origin="lower", extent=extent, cmap="viridis")
    ax1.set_title("Group Full-Spectrum Coherence (A-H)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Frequency (Hz)")
    fig1.colorbar(im, ax=ax1, label="Coherence")
    fig1.tight_layout()
    fig1.savefig(coh_png, bbox_inches="tight")
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    ax2.plot(freqs_gc, group_gc_a, color="#4d4d4d", lw=2.2, label="A→H")
    ax2.fill_between(freqs_gc, group_gc_a - gc_a_sem, group_gc_a + gc_a_sem, color="#4d4d4d", alpha=0.2)
    ax2.plot(freqs_gc, group_gc_h, color="#2f6fbd", lw=2.2, label="H→A")
    ax2.fill_between(freqs_gc, group_gc_h - gc_h_sem, group_gc_h + gc_h_sem, color="#2f6fbd", alpha=0.2)
    ax2.set_title("Group Full-Spectrum Spectral GC")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Granger index")
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.25)
    ax2.legend(frameon=False)
    if sig_spans:
        ax2.text(0.02, 0.97, "Uncorrected p<0.05 spans shown in summary", transform=ax2.transAxes, va="top", fontsize=8)
    fig2.tight_layout()
    fig2.savefig(sgc_png, bbox_inches="tight")
    plt.close(fig2)

    fig3 = plt.figure(figsize=(14.0, 5.2), dpi=220)
    gs = fig3.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.6, left=0.08, right=0.95, bottom=0.15, top=0.78)

    axc = fig3.add_subplot(gs[0, 0])
    im2 = axc.imshow(group_coh, aspect="auto", origin="lower", extent=extent, cmap="viridis", interpolation="gaussian")
    axc.set_title("A  Coherence (A-H)", loc="left", fontsize=13, fontweight="bold", pad=25)
    axc.set_xlabel("Time (s)")
    axc.set_ylabel("Frequency (Hz)")
    fig3.colorbar(im2, ax=axc, fraction=0.046, pad=0.04, label="Coherence")

    axa = fig3.add_subplot(gs[0, 1])
    axa.plot(freqs_gc, group_gc_a, color="#4d4d4d", lw=2.0)
    axa.fill_between(freqs_gc, group_gc_a - gc_a_sem, group_gc_a + gc_a_sem, color="#4d4d4d", alpha=0.2)
    axa.set_title("B  Spectral Granger Causality\nA→H", loc="left", fontsize=13, fontweight="bold", pad=25)
    axa.set_xlabel("Frequency (Hz)")
    axa.set_ylabel("Granger index")
    axa.set_xlim(2, 45)
    axa.grid(alpha=0.25)

    axh = fig3.add_subplot(gs[0, 2])
    axh.plot(freqs_gc, group_gc_h, color="#2f6fbd", lw=2.0)
    axh.fill_between(freqs_gc, group_gc_h - gc_h_sem, group_gc_h + gc_h_sem, color="#2f6fbd", alpha=0.2)
    axh.set_title("H→A", fontsize=12, fontweight="bold")
    axh.set_xlabel("Frequency (Hz)")
    axh.set_xlim(2, 45)
    axh.grid(alpha=0.25)

    fig3.suptitle(f"Group full-spectrum arousal connectivity (n={len(used_files)} runs)", fontsize=11, y=0.98)
    fig3.savefig(combo_png, bbox_inches="tight")
    plt.close(fig3)

    fig4, ax4 = plt.subplots(figsize=(7.2, 3.0), dpi=220)
    ax4.plot(freqs_gc, pvals, color="#555555", lw=1.5, label="p-value")
    ax4.axhline(0.05, color="#888888", ls="--", lw=1.0, label="0.05")
    for lo, hi in sig_spans:
        ax4.axvspan(lo, hi, color="#ef476f", alpha=0.18, lw=0)
    ax4.set_yscale("log")
    ax4.set_ylim(1e-6, 1)
    ax4.set_xlim(2, 45)
    ax4.set_xlabel("Frequency (Hz)")
    ax4.set_ylabel("paired p-value (log)")
    ax4.set_title("A→H vs H→A significance by frequency")
    ax4.grid(alpha=0.25)
    ax4.legend(frameon=False)
    fig4.tight_layout()
    fig4.savefig(sig_png, bbox_inches="tight")
    plt.close(fig4)

    return {
        "coherence_png": str(coh_png),
        "sgc_png": str(sgc_png),
        "combo_png": str(combo_png),
        "significance_png": str(sig_png),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full-spectrum coherence + spectral GC for AI arousal events across all NWB subjects")
    p.add_argument("--arousal-csv", type=Path, required=True, help="AI arousal segments CSV with start_sec/end_sec/center_sec")
    p.add_argument("--data-dir", type=Path, required=True, help="Directory containing subject NWB files")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    p.add_argument("--win-ms", type=float, default=500.0, help="Sliding coherence window (ms)")
    p.add_argument("--step-ms", type=float, default=10.0, help="Sliding coherence step (ms)")
    p.add_argument("--subwin-ms", type=float, default=250.0, help="Welch sub-window inside each big window (ms)")
    p.add_argument("--sub-ovlp", type=float, default=0.5, help="Welch overlap ratio (0-0.9)")
    p.add_argument("--gc-lags", type=int, default=20, help="GC lag parameter")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_dir = args.output_dir / "connectivity_arousal_fullspectrum"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.arousal_csv.exists():
        raise FileNotFoundError(f"Missing arousal CSV: {args.arousal_csv}")

    arousal_df = pd.read_csv(args.arousal_csv)
    if "center_sec" not in arousal_df.columns:
        raise ValueError(f"{args.arousal_csv} must contain center_sec")

    nwb_files = iter_nwb_files(args.data_dir)
    if not nwb_files:
        raise FileNotFoundError(f"No .nwb files found in {args.data_dir}")

    coh_stack = []
    gc_a_stack = []
    gc_h_stack = []
    used_files: list[str] = []
    skipped_files: list[str] = []
    ref_freqs_coh = ref_time_coh = ref_freqs_gc = None

    for idx, nwb_path in enumerate(nwb_files, start=1):
        print(f"[{idx}/{len(nwb_files)}] {nwb_path.name}", flush=True)
        try:
            sig = load_subject_lfp_from_nwb(nwb_path)
            cfg = PipelineConfig(data_dir=nwb_path.parent.parent, output_dir=out_dir, event_csv=None)
            sig_pp = preprocess_signal(sig, cfg)
            events = _build_arousal_events(args.arousal_csv, sig_pp.subject)
            ep = epoch_subject(sig_pp, events, cfg)
            clean_ep, _ = run_hybrid_qc(ep, cfg)
            pairs, amyg_idx, hip_idx = _pick_region_pairs(clean_ep.channel_names, sig_pp.region)
            if not amyg_idx or not hip_idx:
                raise ValueError("No A/H channels after QC")

            freqs_coh, time_coh, coh_tf = compute_sliding_coherence_full(
                ep_data=clean_ep.data,
                sfreq=clean_ep.sfreq,
                amyg_idx=amyg_idx,
                hip_idx=hip_idx,
                times=clean_ep.times,
                freq_range=(2.0, 45.0),
                win_ms=args.win_ms,
                step_ms=args.step_ms,
                subwin_ms=args.subwin_ms,
                sub_ovlp=args.sub_ovlp,
            )
            freqs_gc, gc_a2h, gc_h2a = compute_full_spectral_gc(
                ep_data=clean_ep.data,
                sfreq=clean_ep.sfreq,
                amyg_idx=amyg_idx,
                hip_idx=hip_idx,
                fmin=2.0,
                fmax=45.0,
                gc_n_lags=args.gc_lags,
            )

            if ref_freqs_coh is None:
                ref_freqs_coh = freqs_coh
                ref_time_coh = time_coh
                ref_freqs_gc = freqs_gc
            coh_stack.append(coh_tf)
            gc_a_stack.append(gc_a2h)
            gc_h_stack.append(gc_h2a)
            used_files.append(nwb_path.name)

            base = f"{sig_pp.subject}_{nwb_path.stem.lower()}_arousal_fullspectrum"
            savemat(
                out_dir / f"{base}.mat",
                {
                    "subject": sig_pp.subject,
                    "n_trials_clean": int(clean_ep.data.shape[0]),
                    "n_channels": int(clean_ep.data.shape[1]),
                    "n_pairs": int(len(pairs)),
                    "freqs_coh": freqs_coh,
                    "time_coh": time_coh,
                    "coh_tf": coh_tf,
                    "freqs_gc": freqs_gc,
                    "gc_a2h": gc_a2h,
                    "gc_h2a": gc_h2a,
                    "n_arousal_segments": int(len(arousal_df)),
                },
                do_compression=True,
            )
        except Exception as exc:
            skipped_files.append(f"{nwb_path.name}: {exc}")
            print(f"  skipped: {exc}", flush=True)

    if not coh_stack or ref_freqs_coh is None or ref_time_coh is None or ref_freqs_gc is None:
        raise RuntimeError("No valid full-spectrum arousal results were produced")

    coh_stack_arr = np.stack(coh_stack, axis=0)
    gc_a_stack_arr = np.stack(gc_a_stack, axis=0)
    gc_h_stack_arr = np.stack(gc_h_stack, axis=0)

    figs = _plot_group_full_spectrum(
        out_dir=out_dir,
        freqs_coh=ref_freqs_coh,
        time_coh=ref_time_coh,
        coh_stack=coh_stack_arr,
        freqs_gc=ref_freqs_gc,
        gc_a_stack=gc_a_stack_arr,
        gc_h_stack=gc_h_stack_arr,
        used_files=used_files,
    )

    summary = {
        "n_subjects": int(len(nwb_files)),
        "n_success": int(len(used_files)),
        "n_failed": int(len(skipped_files)),
        "n_arousal_segments": int(len(arousal_df)),
        "n_freqs_coh": int(len(ref_freqs_coh)),
        "n_freqs_gc": int(len(ref_freqs_gc)),
        "mean_coherence": float(np.nanmean(coh_stack_arr)),
        "mean_a_to_h_gc": float(np.nanmean(gc_a_stack_arr)),
        "mean_h_to_a_gc": float(np.nanmean(gc_h_stack_arr)),
        "used_files": used_files,
        "skipped_files": skipped_files,
        **figs,
    }
    summary_path = args.output_dir / "arousal_fullspectrum_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"saved {summary_path}")
    print(f"saved figures under {out_dir}")


if __name__ == "__main__":
    main()
