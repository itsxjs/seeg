from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import scipy.signal as sps
from mne_connectivity import spectral_connectivity_epochs
from scipy.io import savemat

from ah_pipeline.config import PipelineConfig
from ah_pipeline.nwb_io import load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc


def _pick_region_pairs(channel_names: list[str], regions: list[str]) -> tuple[list[tuple[int, int, str]], list[int], list[int]]:
    amyg = [(idx, name) for idx, (name, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "amygdala"]
    hipp = [(idx, name) for idx, (name, rg) in enumerate(zip(channel_names, regions, strict=True)) if rg == "hippocampus"]

    pairs: list[tuple[int, int, str]] = []
    for idx_a, name_a in amyg:
        for idx_h, name_h in hipp:
            pairs.append((idx_a, idx_h, f"{name_a}__{name_h}"))

    return pairs, [idx for idx, _ in amyg], [idx for idx, _ in hipp]


def compute_sliding_coherence_full(
    ep_data: np.ndarray,
    sfreq: float,
    amyg_idx: list[int],
    hip_idx: list[int],
    times: np.ndarray,
    freq_range: tuple[float, float] = (2.0, 45.0),
    win_ms: float = 500.0,
    step_ms: float = 10.0,
    subwin_ms: float = 250.0,
    sub_ovlp: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import time as _time

    n_trials, _, n_time = ep_data.shape
    if n_trials == 0:
        raise ValueError("No clean trials available for coherence")
    if len(amyg_idx) == 0 or len(hip_idx) == 0:
        raise ValueError("No amygdala/hippocampus channels available for coherence")

    # Fast path for one-subject preview: use ROI-mean signals (Amy vs Hip) per trial
    # instead of exhaustive pairwise loops (trial x window x pair), which can be extremely slow.
    amyg_trial = ep_data[:, amyg_idx, :].mean(axis=1)
    hip_trial = ep_data[:, hip_idx, :].mean(axis=1)

    win_samp = int(round(win_ms * sfreq / 1000.0))
    step_samp = int(round(step_ms * sfreq / 1000.0))
    subwin_samp = max(8, int(round(subwin_ms * sfreq / 1000.0)))
    subwin_samp = min(subwin_samp, max(win_samp - 1, 8))
    noverlap = int(round(subwin_samp * sub_ovlp))
    noverlap = min(max(noverlap, 0), subwin_samp - 1)
    nfft = 2 ** int(np.ceil(np.log2(subwin_samp)))

    win_starts = np.arange(0, n_time - win_samp + 1, step_samp, dtype=int)
    if win_starts.size == 0:
        raise ValueError("Windowing produced no valid windows; check epoch/window settings")

    sample_x = amyg_trial[0, win_starts[0] : win_starts[0] + win_samp]
    sample_y = hip_trial[0, win_starts[0] : win_starts[0] + win_samp]
    freq_full, _ = sps.coherence(sample_x, sample_y, fs=sfreq, nperseg=subwin_samp, noverlap=noverlap, nfft=nfft)
    keep = (freq_full >= freq_range[0]) & (freq_full <= freq_range[1])
    freqs = freq_full[keep]

    coh_tf = np.full((len(freqs), len(win_starts)), np.nan, dtype=float)
    time_vec = np.full(len(win_starts), np.nan, dtype=float)

    t0 = _time.time()
    for wi, start in enumerate(win_starts):
        end = start + win_samp
        time_vec[wi] = float(np.mean(times[start:end]))
        accum = np.zeros(len(freqs), dtype=float)

        for tr in range(n_trials):
            x = sps.detrend(amyg_trial[tr, start:end], type="linear")
            y = sps.detrend(hip_trial[tr, start:end], type="linear")
            _, cxy = sps.coherence(
                x,
                y,
                fs=sfreq,
                nperseg=subwin_samp,
                noverlap=noverlap,
                nfft=nfft,
            )
            accum += np.nan_to_num(cxy[keep], nan=0.0)

        coh_tf[:, wi] = accum / n_trials

        if (wi + 1) % max(1, len(win_starts) // 10) == 0 or wi == 0 or wi + 1 == len(win_starts):
            elapsed = _time.time() - t0
            frac = (wi + 1) / len(win_starts)
            eta = (elapsed / frac) - elapsed if frac > 0 else np.nan
            print(
                f"  coherence windows: {wi + 1}/{len(win_starts)} "
                f"({frac * 100:4.1f}%) elapsed={elapsed:6.1f}s eta={eta:6.1f}s",
                flush=True,
            )

    return freqs, time_vec, coh_tf


def compute_full_spectral_gc(
    ep_data: np.ndarray,
    sfreq: float,
    amyg_idx: list[int],
    hip_idx: list[int],
    fmin: float = 2.0,
    fmax: float = 45.0,
    gc_n_lags: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(amyg_idx) == 0 or len(hip_idx) == 0:
        raise ValueError("Need both amygdala and hippocampus channels for spectral GC")

    pick_idx = amyg_idx + hip_idx
    data_sel = ep_data[:, pick_idx, :].astype(np.float64)

    seed = list(range(len(amyg_idx)))
    target = list(range(len(amyg_idx), len(pick_idx)))

    indices_a2h = (np.array([seed]), np.array([target]))
    indices_h2a = (np.array([target]), np.array([seed]))

    con_a2h = spectral_connectivity_epochs(
        data_sel,
        sfreq=sfreq,
        method="gc",
        indices=indices_a2h,
        mode="multitaper",
        fmin=fmin,
        fmax=fmax,
        gc_n_lags=gc_n_lags,
        n_jobs=1,
        verbose=False,
    )
    con_h2a = spectral_connectivity_epochs(
        data_sel,
        sfreq=sfreq,
        method="gc",
        indices=indices_h2a,
        mode="multitaper",
        fmin=fmin,
        fmax=fmax,
        gc_n_lags=gc_n_lags,
        n_jobs=1,
        verbose=False,
    )

    freqs = np.asarray(con_a2h.freqs, dtype=float)
    a2h = np.asarray(con_a2h.get_data()).reshape(-1)
    h2a = np.asarray(con_h2a.get_data()).reshape(-1)
    return freqs, a2h, h2a


def plot_literature_style(
    freqs_coh: np.ndarray,
    time_coh: np.ndarray,
    coh_tf: np.ndarray,
    freqs_gc: np.ndarray,
    gc_a2h: np.ndarray,
    gc_h2a: np.ndarray,
    subject: str,
    out_png: Path,
) -> None:
    fig = plt.figure(figsize=(10.5, 4.8), dpi=200)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    extent = [float(time_coh.min()), float(time_coh.max()), float(freqs_coh.min()), float(freqs_coh.max())]
    im = ax1.imshow(coh_tf, aspect="auto", origin="lower", extent=extent, cmap="viridis")
    ax1.set_title("A  Coherence (A-H)", loc="left", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Frequency (Hz)")
    ax1.set_yticks([2, 4, 8, 12, 28, 45])
    cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label("Coherence")

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(freqs_gc, gc_a2h, color="#4d4d4d", lw=2.0, label="neutral")
    ax2.set_title("B  Spectral Granger Causality\nA→H", loc="left", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Granger index")
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.25)
    ax2.legend(frameon=False, loc="upper right")

    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(freqs_gc, gc_h2a, color="#4d4d4d", lw=2.0, label="neutral")
    ax3.set_title("H→A", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_xlim(2, 45)
    ax3.grid(alpha=0.25)

    fig.suptitle(
        f"{subject} full-spectrum connectivity (no valence split)",
        fontsize=11,
        y=0.99,
    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full-spectrum coherence + spectral GC on one subject (no valence split)")
    p.add_argument("--nwb-path", type=Path, required=True, help="Path to one .nwb file")
    p.add_argument("--event-csv", type=Path, required=True, help="Event CSV with subject/onset columns")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    p.add_argument("--win-ms", type=float, default=500.0, help="Sliding coherence window (ms)")
    p.add_argument("--step-ms", type=float, default=10.0, help="Sliding coherence step (ms)")
    p.add_argument("--subwin-ms", type=float, default=250.0, help="Welch sub-window inside each big window (ms)")
    p.add_argument("--sub-ovlp", type=float, default=0.5, help="Welch overlap ratio (0-0.9)")
    p.add_argument("--gc-lags", type=int, default=20, help="GC lag parameter")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("[1/6] loading subject LFP", flush=True)

    cfg = PipelineConfig(
        data_dir=args.nwb_path.parent.parent,
        event_csv=args.event_csv,
        output_dir=args.output_dir,
    )

    subject_sig = load_subject_lfp_from_nwb(args.nwb_path)
    print("[2/6] preprocessing", flush=True)
    preprocessed = preprocess_signal(subject_sig, cfg)

    print("[3/6] epoching + QC", flush=True)
    events = load_events(args.event_csv)
    epochs = epoch_subject(preprocessed, events, cfg)
    clean_ep, qc = run_hybrid_qc(epochs, cfg)

    pairs, amyg_idx, hip_idx = _pick_region_pairs(clean_ep.channel_names, preprocessed.region)

    print("[4/6] sliding full-spectrum coherence", flush=True)
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

    print("[5/6] spectral GC", flush=True)
    freqs_gc, gc_a2h, gc_h2a = compute_full_spectral_gc(
        ep_data=clean_ep.data,
        sfreq=clean_ep.sfreq,
        amyg_idx=amyg_idx,
        hip_idx=hip_idx,
        fmin=2.0,
        fmax=45.0,
        gc_n_lags=args.gc_lags,
    )

    base = f"{clean_ep.subject}_{args.nwb_path.stem.lower()}_fullspectrum"
    out_png = args.output_dir / f"{base}.png"
    out_mat = args.output_dir / f"{base}.mat"

    print("[6/6] plotting + saving", flush=True)
    plot_literature_style(
        freqs_coh=freqs_coh,
        time_coh=time_coh,
        coh_tf=coh_tf,
        freqs_gc=freqs_gc,
        gc_a2h=gc_a2h,
        gc_h2a=gc_h2a,
        subject=clean_ep.subject,
        out_png=out_png,
    )

    savemat(
        out_mat,
        {
            "subject": clean_ep.subject,
            "n_trials_clean": int(clean_ep.data.shape[0]),
            "n_channels": int(clean_ep.data.shape[1]),
            "n_pairs": int(len(pairs)),
            "freqs_coh": freqs_coh,
            "time_coh": time_coh,
            "coh_tf": coh_tf,
            "freqs_gc": freqs_gc,
            "gc_a2h": gc_a2h,
            "gc_h2a": gc_h2a,
            "qc_keep_idx": qc["keep_idx"],
            "qc_reject_idx": qc["reject_idx"],
        },
        do_compression=True,
    )

    print(f"subject={clean_ep.subject}")
    print(f"clean_trials={clean_ep.data.shape[0]}")
    print(f"pairs={len(pairs)}")
    print(f"coh_shape={coh_tf.shape}")
    print(f"gc_n_freq={len(freqs_gc)}")
    print(f"saved_png={out_png}")
    print(f"saved_mat={out_mat}")


if __name__ == "__main__":
    main()
