from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.stats import ttest_rel


def _fdr_bh(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    out = np.zeros_like(p, dtype=bool)
    ok = np.isfinite(p)
    if not np.any(ok):
        return out

    idx = np.where(ok)[0]
    pv = p[idx]
    order = np.argsort(pv)
    pv_sorted = pv[order]
    ranks = np.arange(1, len(pv_sorted) + 1)
    thresh = alpha * ranks / len(pv_sorted)
    passed = pv_sorted <= thresh
    if not np.any(passed):
        return out

    kmax = np.max(np.where(passed)[0])
    cutoff = pv_sorted[kmax]
    out[idx] = pv <= cutoff
    return out


def _mask_to_spans(mask: np.ndarray, x: np.ndarray) -> list[tuple[float, float]]:
    mask = np.asarray(mask, dtype=bool)
    x = np.asarray(x, dtype=float)
    spans: list[tuple[float, float]] = []
    start = None
    for i, val in enumerate(mask):
        if val and start is None:
            start = i
        if (not val or i == len(mask) - 1) and start is not None:
            end = i if val and i == len(mask) - 1 else i - 1
            spans.append((float(x[start]), float(x[end])))
            start = None
    return spans


def _perm_upper_threshold(
    values_2d: np.ndarray,
    quantile: float = 0.999,
    n_perm: int = 10000,
    seed: int = 42,
) -> np.ndarray:
    """One-sample sign-flip permutation upper threshold per frequency."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(values_2d, dtype=float)
    n_freq = arr.shape[1]
    threshold = np.full(n_freq, np.nan, dtype=float)

    for fi in range(n_freq):
        x = arr[:, fi]
        x = x[np.isfinite(x)]
        n = len(x)
        if n < 3:
            continue

        signs = rng.choice(np.array([-1.0, 1.0]), size=(n_perm, n), replace=True)
        perm_means = (signs @ x) / n
        threshold[fi] = float(np.quantile(perm_means, quantile))

    return threshold


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot arousal full-spectrum group figure with significant frequency shading")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/Volumes/rmhyw/keles_ah_nwb_pipeline/results/full_spectrum_arousal_all_subjects"),
        help="Root output directory from run_full_spectrum_arousal_all_subjects.py",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=None,
        help="Optional explicit output PNG path",
    )
    return parser.parse_args()


def _collect_subject_mats(mat_dir: Path) -> list[Path]:
    return sorted(
        p for p in mat_dir.glob("*_arousal_fullspectrum.mat")
        if not p.name.startswith("._")
    )


def _load_subject_mats(mat_paths: list[Path]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    if not mat_paths:
        raise FileNotFoundError("No *_arousal_fullspectrum.mat files found")

    coh_list: list[np.ndarray] = []
    a_list: list[np.ndarray] = []
    h_list: list[np.ndarray] = []
    used: list[str] = []
    ref_freqs_coh = ref_times_coh = ref_freqs_gc = None

    for mat_path in mat_paths:
        try:
            mat = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
            coh_tf = np.asarray(mat["coh_tf"], dtype=float)
            freqs_coh = np.asarray(mat["freqs_coh"], dtype=float).reshape(-1)
            time_coh = np.asarray(mat["time_coh"], dtype=float).reshape(-1)
            freqs_gc = np.asarray(mat["freqs_gc"], dtype=float).reshape(-1)
            gc_a2h = np.asarray(mat["gc_a2h"], dtype=float).reshape(-1)
            gc_h2a = np.asarray(mat["gc_h2a"], dtype=float).reshape(-1)
        except Exception:
            continue

        if ref_freqs_coh is None:
            ref_freqs_coh = freqs_coh
            ref_times_coh = time_coh
            ref_freqs_gc = freqs_gc

        if not np.allclose(freqs_coh, ref_freqs_coh) or not np.allclose(time_coh, ref_times_coh) or not np.allclose(freqs_gc, ref_freqs_gc):
            continue

        coh_list.append(coh_tf)
        a_list.append(gc_a2h)
        h_list.append(gc_h2a)
        used.append(mat_path.name)

    if not coh_list or ref_freqs_coh is None or ref_times_coh is None or ref_freqs_gc is None:
        raise RuntimeError("No compatible full-spectrum arousal MAT files were loaded")

    return (
        np.stack(coh_list, axis=0),
        np.stack(a_list, axis=0),
        np.stack(h_list, axis=0),
        ref_freqs_coh,
        ref_times_coh,
        ref_freqs_gc,
        used,
    )


def main() -> None:
    args = parse_args()
    mat_dir = args.input_dir / "connectivity_arousal_fullspectrum"
    mat_paths = _collect_subject_mats(mat_dir)
    coh_stack, a_stack, h_stack, ref_freqs_coh, ref_times_coh, ref_freqs_gc, used = _load_subject_mats(mat_paths)

    group_coh = np.nanmean(coh_stack, axis=0)
    group_gc_a = np.nanmean(a_stack, axis=0)
    group_gc_h = np.nanmean(h_stack, axis=0)
    gc_a_sem = np.nanstd(a_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(a_stack), axis=0), 1))
    gc_h_sem = np.nanstd(h_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(h_stack), axis=0), 1))
    perm_thr_a = _perm_upper_threshold(a_stack, quantile=0.999, n_perm=10000, seed=42)
    perm_thr_h = _perm_upper_threshold(h_stack, quantile=0.999, n_perm=10000, seed=43)

    pvals = np.full(len(ref_freqs_gc), np.nan, dtype=float)
    for fi in range(len(ref_freqs_gc)):
        a = a_stack[:, fi]
        h = h_stack[:, fi]
        ok = np.isfinite(a) & np.isfinite(h)
        if np.sum(ok) < 3:
            continue
        _, pvals[fi] = ttest_rel(a[ok], h[ok], nan_policy="omit")

    sig_mask = np.isfinite(pvals) & (pvals < 0.05)
    sig_fdr = _fdr_bh(pvals, alpha=0.05)
    sig_spans = _mask_to_spans(sig_fdr, ref_freqs_gc)

    output_png = args.output_png or (args.input_dir / "connectivity_arousal_fullspectrum" / "group_fullspectrum_arousal_sgc_overlay_sigshade.png")
    output_png.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=220)
    ax.plot(ref_freqs_gc, group_gc_a, color="#4d4d4d", lw=2.4, label="A→H")
    ax.fill_between(ref_freqs_gc, group_gc_a - gc_a_sem, group_gc_a + gc_a_sem, color="#4d4d4d", alpha=0.18)
    ax.plot(ref_freqs_gc, perm_thr_a, color="#4d4d4d", lw=1.2, ls="--", alpha=0.9, label="A→H perm 99.9%")
    ax.plot(ref_freqs_gc, group_gc_h, color="#2f6fbd", lw=2.4, label="H→A")
    ax.fill_between(ref_freqs_gc, group_gc_h - gc_h_sem, group_gc_h + gc_h_sem, color="#2f6fbd", alpha=0.18)
    ax.plot(ref_freqs_gc, perm_thr_h, color="#2f6fbd", lw=1.2, ls="--", alpha=0.9, label="H→A perm 99.9%")
    for lo, hi in sig_spans:
        ax.axvspan(lo, hi, color="#ef476f", alpha=0.18, lw=0)
    ax.set_title(f"Group full-spectrum arousal connectivity (n={len(used)} runs)")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Granger index")
    ax.set_xlim(2, 45)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper right")
    ax.text(0.02, 0.98, "Shaded: A→H vs H→A, paired t-test FDR q<0.05", transform=ax.transAxes, va="top", fontsize=9)

    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    print(f"saved {output_png}")
    print(f"significant bins (uncorrected p<0.05): {int(np.sum(sig_mask))}")
    print(f"significant spans (FDR q<0.05): {len(sig_spans)}")


if __name__ == "__main__":
    main()
