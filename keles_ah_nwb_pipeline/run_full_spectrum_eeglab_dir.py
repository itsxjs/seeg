from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import mne
import numpy as np
import scipy.signal as sps
from mne_connectivity import spectral_connectivity_epochs
from scipy.io import loadmat, savemat


ROI_MAP = {
    "sub001": {
        "A": ["A2-Ref"],
        "H": ["A1-Ref", "POL B1", "C1-Ref", "C2-Ref", "C3-Ref"],
    },
    "sub004": {
        "A": ["A1-Ref", "A2-Ref", "POL A3", "POL A4", "POL A5"],
        "H": ["POL B1", "POL B2", "POL B3", "POL B4", "C2-Ref", "C3-Ref", "C4-Ref"],
    },
    "sub005": {
        "A": ["A1-Ref", "A2-Ref", "POL A3", "POL L7", "POL L8", "POL L9", "POL L10"],
        "H": ["POL B1", "POL B2", "POL L13", "POL L14"],
    },
    "sub007": {
        "A": ["A1-Ref", "A2-Ref", "POL A3", "POL A4"],
        "H": ["POL B3", "POL B4", "C1-Ref", "POL B1", "POL B2", "C2-Ref", "C3-Ref", "C4-Ref", "F2-Ref", "F3-Ref", "F4-Ref"],
    },
    "sub008": {
        "A": ["A1-Ref", "A2-Ref", "POL A3", "POL A4", "POL A5"],
        "H": ["POL B1", "POL B2", "C1-Ref", "C2-Ref", "C3-Ref"],
    },
    "sub009": {
        "A": ["A1-Ref", "A2-Ref", "POL A3"],
        "H": ["POL B1", "POL B2", "POL B3"],
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Full-spectrum coherence + sGC from EEGLAB epoch_clean.set directory")
    p.add_argument("--dataset-dir", type=Path, required=True)
    p.add_argument("--output-subdir", type=str, default="full_spectrum_python")
    p.add_argument("--glob-pattern", type=str, default="sub*_valence_epoch_clean.set")
    p.add_argument("--gc-lags", type=int, default=20)
    return p.parse_args()


def _subject_from_name(name: str) -> str | None:
    m = re.search(r"(sub\d+)", name.lower())
    return m.group(1) if m else None


def compute_sliding_coh_roi_mean(
    data: np.ndarray,
    sfreq: float,
    times: np.ndarray,
    amyg_idx: list[int],
    hip_idx: list[int],
    win_ms: float = 500.0,
    step_ms: float = 10.0,
    subwin_ms: float = 250.0,
    sub_ovlp: float = 0.5,
    freq_range: tuple[float, float] = (2.0, 45.0),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_epochs, _, n_time = data.shape
    if n_epochs == 0:
        raise ValueError("No epochs")

    am = data[:, amyg_idx, :].mean(axis=1)
    hp = data[:, hip_idx, :].mean(axis=1)

    win = int(round(win_ms * sfreq / 1000.0))
    step = int(round(step_ms * sfreq / 1000.0))
    subwin = max(8, int(round(subwin_ms * sfreq / 1000.0)))
    subwin = min(subwin, max(win - 1, 8))
    noverlap = int(round(subwin * sub_ovlp))
    noverlap = min(max(noverlap, 0), subwin - 1)
    nfft = 2 ** int(np.ceil(np.log2(subwin)))

    starts = np.arange(0, n_time - win + 1, step, dtype=int)
    if len(starts) == 0:
        raise ValueError("No sliding windows")

    f0, c0 = sps.coherence(am[0, starts[0] : starts[0] + win], hp[0, starts[0] : starts[0] + win], fs=sfreq, nperseg=subwin, noverlap=noverlap, nfft=nfft)
    keep = (f0 >= freq_range[0]) & (f0 <= freq_range[1])
    freqs = f0[keep]

    coh_tf = np.full((len(freqs), len(starts)), np.nan, dtype=float)
    tvec = np.array([float(np.mean(times[s : s + win])) for s in starts], dtype=float)

    for wi, s in enumerate(starts):
        e = s + win
        accum = np.zeros(len(freqs), dtype=float)
        for ei in range(n_epochs):
            x = sps.detrend(am[ei, s:e], type="linear")
            y = sps.detrend(hp[ei, s:e], type="linear")
            _, cxy = sps.coherence(x, y, fs=sfreq, nperseg=subwin, noverlap=noverlap, nfft=nfft)
            accum += np.nan_to_num(cxy[keep], nan=0.0)
        coh_tf[:, wi] = accum / n_epochs

    return freqs, tvec, coh_tf


def compute_sgc_multivar(data: np.ndarray, sfreq: float, amyg_idx: list[int], hip_idx: list[int], gc_lags: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pick = amyg_idx + hip_idx
    data_sel = data[:, pick, :].astype(np.float64)

    seed = list(range(len(amyg_idx)))
    target = list(range(len(amyg_idx), len(pick)))

    idx_a2h = (np.array([seed]), np.array([target]))
    idx_h2a = (np.array([target]), np.array([seed]))

    con_a2h = spectral_connectivity_epochs(
        data_sel,
        sfreq=sfreq,
        method="gc",
        indices=idx_a2h,
        mode="multitaper",
        fmin=2,
        fmax=45,
        gc_n_lags=gc_lags,
        n_jobs=1,
        verbose=False,
    )
    con_h2a = spectral_connectivity_epochs(
        data_sel,
        sfreq=sfreq,
        method="gc",
        indices=idx_h2a,
        mode="multitaper",
        fmin=2,
        fmax=45,
        gc_n_lags=gc_lags,
        n_jobs=1,
        verbose=False,
    )

    f = np.asarray(con_a2h.freqs, dtype=float)
    a2h = np.asarray(con_a2h.get_data()).reshape(-1)
    h2a = np.asarray(con_h2a.get_data()).reshape(-1)
    return f, a2h, h2a


def save_subject_plot(out_png: Path, subject: str, fcoh: np.ndarray, tcoh: np.ndarray, coh_tf: np.ndarray, fgc: np.ndarray, a2h: np.ndarray, h2a: np.ndarray) -> None:
    fig = plt.figure(figsize=(10.6, 4.8), dpi=200)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    extent = [float(tcoh.min()), float(tcoh.max()), float(fcoh.min()), float(fcoh.max())]
    im = ax1.imshow(coh_tf, aspect="auto", origin="lower", extent=extent, cmap="viridis")
    ax1.set_title("A  Coherence (A-H)", loc="left", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Frequency (Hz)")
    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04, label="Coherence")

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(fgc, a2h, color="#4d4d4d", lw=2)
    ax2.set_title("B  Spectral Granger Causality\nA→H", loc="left", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Granger index")
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.25)

    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(fgc, h2a, color="#2f6fbd", lw=2)
    ax3.set_title("H→A", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_xlim(2, 45)
    ax3.grid(alpha=0.25)

    fig.suptitle(f"{subject} full-spectrum (no condition split)", fontsize=11, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png)
    plt.close(fig)


def _perm_upper_threshold(values_2d: np.ndarray, quantile: float = 0.999, n_perm: int = 10000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    arr = np.asarray(values_2d, dtype=float)
    n_freq = arr.shape[1]
    threshold = np.full(n_freq, np.nan, dtype=float)

    for fi in range(n_freq):
        x = arr[:, fi]
        x = x[np.isfinite(x)]
        n = len(x)
        if n < 2:
            continue
        signs = rng.choice(np.array([-1.0, 1.0]), size=(n_perm, n), replace=True)
        perm_means = (signs @ x) / n
        threshold[fi] = float(np.quantile(perm_means, quantile))

    return threshold


def plot_group(out_dir: Path, mats: list[Path]) -> None:
    if not mats:
        return

    coh_list = []
    a_list = []
    h_list = []
    used = []

    ref_fcoh = ref_tcoh = ref_fgc = None

    for p in mats:
        try:
            m = loadmat(p, squeeze_me=True, struct_as_record=False)
            coh_tf = np.asarray(m["coh_tf"], dtype=float)
            fcoh = np.asarray(m["freqs_coh"], dtype=float).reshape(-1)
            tcoh = np.asarray(m["time_coh"], dtype=float).reshape(-1)
            fgc = np.asarray(m["freqs_gc"], dtype=float).reshape(-1)
            a = np.asarray(m["gc_a2h"], dtype=float).reshape(-1)
            h = np.asarray(m["gc_h2a"], dtype=float).reshape(-1)
            if ref_fcoh is None:
                ref_fcoh, ref_tcoh, ref_fgc = fcoh, tcoh, fgc

            # Coherence interp to ref grid
            if coh_tf.shape != (len(ref_fcoh), len(ref_tcoh)) or not np.allclose(fcoh, ref_fcoh) or not np.allclose(tcoh, ref_tcoh):
                coh_t = np.full((coh_tf.shape[0], len(ref_tcoh)), np.nan)
                for fi in range(coh_tf.shape[0]):
                    y = coh_tf[fi]
                    if np.sum(np.isfinite(y)) >= 2:
                        coh_t[fi] = np.interp(ref_tcoh, tcoh, np.nan_to_num(y, nan=np.nanmedian(y[np.isfinite(y)])))
                coh_ref = np.full((len(ref_fcoh), len(ref_tcoh)), np.nan)
                for ti in range(len(ref_tcoh)):
                    y = coh_t[:, ti]
                    if np.sum(np.isfinite(y)) >= 2:
                        coh_ref[:, ti] = np.interp(ref_fcoh, fcoh, np.nan_to_num(y, nan=np.nanmedian(y[np.isfinite(y)])))
            else:
                coh_ref = coh_tf

            if len(fgc) != len(ref_fgc) or not np.allclose(fgc, ref_fgc):
                ok_a = np.isfinite(fgc) & np.isfinite(a)
                ok_h = np.isfinite(fgc) & np.isfinite(h)
                a_ref = np.interp(ref_fgc, fgc[ok_a], a[ok_a]) if np.sum(ok_a) >= 2 else np.full_like(ref_fgc, np.nan)
                h_ref = np.interp(ref_fgc, fgc[ok_h], h[ok_h]) if np.sum(ok_h) >= 2 else np.full_like(ref_fgc, np.nan)
            else:
                a_ref, h_ref = a, h

            coh_list.append(coh_ref)
            a_list.append(a_ref)
            h_list.append(h_ref)
            used.append(p.name)
        except Exception:
            continue

    if not coh_list:
        return

    coh_stack = np.stack(coh_list, axis=0)
    a_stack = np.stack(a_list, axis=0)
    h_stack = np.stack(h_list, axis=0)

    gcoh = np.nanmean(coh_stack, axis=0)
    ga = np.nanmean(a_stack, axis=0)
    gh = np.nanmean(h_stack, axis=0)
    a_sem = np.nanstd(a_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(a_stack), axis=0), 1))
    h_sem = np.nanstd(h_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(h_stack), axis=0), 1))
    a_cl = _perm_upper_threshold(a_stack, quantile=0.999, n_perm=10000, seed=42)
    h_cl = _perm_upper_threshold(h_stack, quantile=0.999, n_perm=10000, seed=43)

    # group coherence
    fig1, ax1 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    extent = [float(ref_tcoh.min()), float(ref_tcoh.max()), float(ref_fcoh.min()), float(ref_fcoh.max())]
    im = ax1.imshow(gcoh, aspect="auto", origin="lower", extent=extent, cmap="viridis")
    ax1.set_title(f"Group Coherence (n={len(used)})")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Frequency (Hz)")
    fig1.colorbar(im, ax=ax1, label="Coherence")
    fig1.tight_layout()
    fig1.savefig(out_dir / "group_fullspectrum_coherence.png")
    plt.close(fig1)

    # group sgc
    fig2, ax2 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    ax2.plot(ref_fgc, ga, color="#4d4d4d", lw=2.2, label="A→H")
    ax2.fill_between(ref_fgc, ga - a_sem, ga + a_sem, color="#4d4d4d", alpha=0.2)
    ax2.plot(ref_fgc, gh, color="#2f6fbd", lw=2.2, label="H→A")
    ax2.fill_between(ref_fgc, gh - h_sem, gh + h_sem, color="#2f6fbd", alpha=0.2)
    ax2.set_title(f"Group Spectral GC (n={len(used)})")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Granger index")
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.25)
    ax2.legend(frameon=False)
    fig2.tight_layout()
    fig2.savefig(out_dir / "group_fullspectrum_sgc.png")
    plt.close(fig2)

    # group sgc + CL lines (permutation 99.9%)
    fig3, ax3 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    ax3.plot(ref_fgc, ga, color="#4d4d4d", lw=2.2, label="A→H")
    ax3.fill_between(ref_fgc, ga - a_sem, ga + a_sem, color="#4d4d4d", alpha=0.2)
    ax3.plot(ref_fgc, a_cl, color="#4d4d4d", lw=1.4, ls="--", alpha=0.9, label="A→H CL (perm 99.9%)")
    ax3.plot(ref_fgc, gh, color="#2f6fbd", lw=2.2, label="H→A")
    ax3.fill_between(ref_fgc, gh - h_sem, gh + h_sem, color="#2f6fbd", alpha=0.2)
    ax3.plot(ref_fgc, h_cl, color="#2f6fbd", lw=1.4, ls="--", alpha=0.9, label="H→A CL (perm 99.9%)")
    ax3.set_title(f"Group Spectral GC + CL (n={len(used)})")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Granger index")
    ax3.set_xlim(2, 45)
    ax3.grid(alpha=0.25)
    ax3.legend(frameon=False)
    fig3.tight_layout()
    fig3.savefig(out_dir / "group_fullspectrum_sgc_with_cl.png")
    plt.close(fig3)

    savemat(
        out_dir / "group_fullspectrum_connectivity.mat",
        {
            "used_files": np.array(used, dtype=object),
            "freqs_coh": ref_fcoh,
            "time_coh": ref_tcoh,
            "group_coh_tf": gcoh,
            "freqs_gc": ref_fgc,
            "group_gc_a2h": ga,
            "group_gc_h2a": gh,
            "group_gc_a2h_sem": a_sem,
            "group_gc_h2a_sem": h_sem,
            "group_gc_a2h_cl_perm_q999": a_cl,
            "group_gc_h2a_cl_perm_q999": h_cl,
        },
        do_compression=True,
    )

    with (out_dir / "group_summary.txt").open("w", encoding="utf-8") as f:
        f.write(f"used_runs={len(used)}\n")
        for nm in used:
            f.write(f"  {nm}\n")


def main() -> None:
    args = parse_args()
    ds_dir = args.dataset_dir
    if not ds_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {ds_dir}")

    out_dir = ds_dir / args.output_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    set_files = sorted(ds_dir.glob(args.glob_pattern))
    if not set_files:
        raise RuntimeError(f"No files matched {args.glob_pattern} in {ds_dir}")

    mats: list[Path] = []
    skipped = []

    print(f"dataset={ds_dir}")
    print(f"found_set_files={len(set_files)}")

    for i, set_path in enumerate(set_files, start=1):
        sub = _subject_from_name(set_path.name)
        print(f"[{i}/{len(set_files)}] {set_path.name}", flush=True)

        if sub is None or sub not in ROI_MAP:
            skipped.append((set_path.name, "no ROI map"))
            print("  skip: no ROI map", flush=True)
            continue

        try:
            ep = mne.read_epochs_eeglab(str(set_path), verbose="ERROR")
            data = ep.get_data()
            sfreq = float(ep.info["sfreq"])
            ch_names = [str(c) for c in ep.ch_names]

            amyg_idx = [ch_names.index(c) for c in ROI_MAP[sub]["A"] if c in ch_names]
            hip_idx = [ch_names.index(c) for c in ROI_MAP[sub]["H"] if c in ch_names]

            if len(amyg_idx) == 0 or len(hip_idx) == 0:
                skipped.append((set_path.name, "ROI channels missing"))
                print("  skip: ROI channels missing", flush=True)
                continue

            fcoh, tcoh, coh_tf = compute_sliding_coh_roi_mean(data, sfreq, ep.times, amyg_idx, hip_idx)
            fgc, ga, gh = compute_sgc_multivar(data, sfreq, amyg_idx, hip_idx, gc_lags=args.gc_lags)

            base = set_path.stem.replace("_valence_epoch_clean", "")
            out_mat = out_dir / f"{base}_fullspectrum.mat"
            out_png = out_dir / f"{base}_fullspectrum.png"

            save_subject_plot(out_png, sub, fcoh, tcoh, coh_tf, fgc, ga, gh)
            savemat(
                out_mat,
                {
                    "subject": sub,
                    "source_set": str(set_path),
                    "n_epochs": int(data.shape[0]),
                    "n_channels": int(data.shape[1]),
                    "freqs_coh": fcoh,
                    "time_coh": tcoh,
                    "coh_tf": coh_tf,
                    "freqs_gc": fgc,
                    "gc_a2h": ga,
                    "gc_h2a": gh,
                    "amyg_idx": np.array(amyg_idx, dtype=int),
                    "hip_idx": np.array(hip_idx, dtype=int),
                    "channel_names": np.array(ch_names, dtype=object),
                },
                do_compression=True,
            )
            mats.append(out_mat)
            print(f"  saved {out_png.name}", flush=True)
        except Exception as e:
            skipped.append((set_path.name, str(e)))
            print(f"  skip: {e}", flush=True)

    plot_group(out_dir, mats)

    with (out_dir / "run_summary.txt").open("w", encoding="utf-8") as f:
        f.write(f"set_files={len(set_files)}\n")
        f.write(f"processed={len(mats)}\n")
        f.write(f"skipped={len(skipped)}\n")
        for name, reason in skipped:
            f.write(f"  {name} :: {reason}\n")

    print(f"processed={len(mats)} skipped={len(skipped)}")
    print(f"saved group plots under {out_dir}")


if __name__ == "__main__":
    main()
