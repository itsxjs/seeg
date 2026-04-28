from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat, savemat
from scipy.stats import ttest_rel


def _interp_coh_to_ref(
    coh_tf: np.ndarray,
    freqs: np.ndarray,
    times: np.ndarray,
    ref_freqs: np.ndarray,
    ref_times: np.ndarray,
) -> np.ndarray:
    if coh_tf.shape == (len(ref_freqs), len(ref_times)) and np.allclose(freqs, ref_freqs) and np.allclose(times, ref_times):
        return coh_tf

    out_t = np.full((coh_tf.shape[0], len(ref_times)), np.nan, dtype=float)
    for fi in range(coh_tf.shape[0]):
        y = coh_tf[fi]
        if np.sum(np.isfinite(y)) < 2:
            continue
        out_t[fi] = np.interp(ref_times, times, np.nan_to_num(y, nan=np.nanmedian(y[np.isfinite(y)])))

    out = np.full((len(ref_freqs), len(ref_times)), np.nan, dtype=float)
    for ti in range(len(ref_times)):
        y = out_t[:, ti]
        if np.sum(np.isfinite(y)) < 2:
            continue
        out[:, ti] = np.interp(ref_freqs, freqs, np.nan_to_num(y, nan=np.nanmedian(y[np.isfinite(y)])))

    return out


def _interp_1d_to_ref(x: np.ndarray, y: np.ndarray, ref_x: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=float).reshape(-1)
    x = np.asarray(x, dtype=float).reshape(-1)
    if len(x) == len(ref_x) and np.allclose(x, ref_x):
        return y
    ok = np.isfinite(x) & np.isfinite(y)
    if np.sum(ok) < 2:
        return np.full_like(ref_x, np.nan, dtype=float)
    return np.interp(ref_x, x[ok], y[ok])


def _fdr_bh(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    out = np.zeros(m, dtype=bool)
    ok = np.isfinite(p)
    if np.sum(ok) == 0:
        return out

    idx = np.where(ok)[0]
    pv = p[ok]
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
    if len(mask) == 0:
        return spans

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
) -> tuple[np.ndarray, np.ndarray]:
    """One-sample sign-flip permutation upper threshold per frequency.

    Parameters
    ----------
    values_2d : np.ndarray
        Shape (n_runs, n_freq), GC values for one direction.
    quantile : float
        Upper quantile for permutation null (e.g., 0.999 for p<0.001 one-sided).
    n_perm : int
        Number of random sign-flip permutations.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    threshold : np.ndarray
        Frequency-wise permutation threshold.
    pvals : np.ndarray
        One-sided permutation p-value of observed mean > null.
    """
    rng = np.random.default_rng(seed)
    arr = np.asarray(values_2d, dtype=float)
    n_freq = arr.shape[1]

    threshold = np.full(n_freq, np.nan, dtype=float)
    pvals = np.full(n_freq, np.nan, dtype=float)

    for fi in range(n_freq):
        x = arr[:, fi]
        x = x[np.isfinite(x)]
        n = len(x)
        if n < 3:
            continue

        obs = float(np.mean(x))
        signs = rng.choice(np.array([-1.0, 1.0]), size=(n_perm, n), replace=True)
        perm_means = (signs @ x) / n

        threshold[fi] = float(np.quantile(perm_means, quantile))
        pvals[fi] = float((np.sum(perm_means >= obs) + 1) / (n_perm + 1))

    return threshold, pvals


def _load_group_connectivity_summary(mat_path: Path) -> dict[str, np.ndarray]:
    mat = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
    return {
        "freqs_coh": np.asarray(mat["freqs_coh"], dtype=float).reshape(-1),
        "time_coh": np.asarray(mat["time_coh"], dtype=float).reshape(-1),
        "group_coh_tf": np.asarray(mat["group_coh_tf"], dtype=float),
        "freqs_gc": np.asarray(mat["freqs_gc"], dtype=float).reshape(-1),
        "group_gc_a2h": np.asarray(mat["group_gc_a2h"], dtype=float).reshape(-1),
        "group_gc_h2a": np.asarray(mat["group_gc_h2a"], dtype=float).reshape(-1),
        "group_gc_a2h_sem": np.asarray(mat["group_gc_a2h_sem"], dtype=float).reshape(-1),
        "group_gc_h2a_sem": np.asarray(mat["group_gc_h2a_sem"], dtype=float).reshape(-1),
        "sgc_pvals": np.asarray(mat.get("sgc_pvals", np.array([])), dtype=float).reshape(-1),
        "sgc_sig_mask_fdr_q05": np.asarray(mat.get("sgc_sig_mask_fdr_q05", np.array([])), dtype=bool).reshape(-1),
        "sgc_n_pairs_per_freq": np.asarray(mat.get("sgc_n_pairs_per_freq", np.array([])), dtype=int).reshape(-1),
        "perm_thr_a2h_q999": np.asarray(
            mat.get("perm_thr_a2h_q999", mat.get("group_gc_a2h_cl_perm_q999", np.array([]))),
            dtype=float,
        ).reshape(-1),
        "perm_thr_h2a_q999": np.asarray(
            mat.get("perm_thr_h2a_q999", mat.get("group_gc_h2a_cl_perm_q999", np.array([]))),
            dtype=float,
        ).reshape(-1),
        "perm_pvals_a2h": np.asarray(mat.get("perm_pvals_a2h", np.array([])), dtype=float).reshape(-1),
        "perm_pvals_h2a": np.asarray(mat.get("perm_pvals_h2a", np.array([])), dtype=float).reshape(-1),
        "perm_sig_mask_a2h_p_lt_0p001": np.asarray(mat.get("perm_sig_mask_a2h_p_lt_0p001", np.array([])), dtype=bool).reshape(-1),
        "perm_sig_mask_h2a_p_lt_0p001": np.asarray(mat.get("perm_sig_mask_h2a_p_lt_0p001", np.array([])), dtype=bool).reshape(-1),
        "used_files": np.asarray(mat.get("used_files", np.array([])), dtype=object).reshape(-1),
        "skipped_files": np.asarray(mat.get("skipped_files", np.array([])), dtype=object).reshape(-1),
    }


def _load_subject_mats(out_dir: Path, mats: list[Path] | None = None) -> tuple[list[Path], list[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    candidates = mats or sorted(
        p for p in out_dir.glob("sub-*_fullspectrum.mat")
        if not p.name.startswith("._") and not p.name.startswith("group_")
    )
    if not candidates:
        raise RuntimeError(f"No subject full-spectrum .mat files found under {out_dir}")

    coh_list: list[np.ndarray] = []
    a_list: list[np.ndarray] = []
    h_list: list[np.ndarray] = []
    used_files: list[str] = []
    skipped_files: list[str] = []
    ref_freqs_coh = ref_times_coh = ref_freqs_gc = None

    for p in candidates:
        try:
            m = loadmat(p, squeeze_me=True, struct_as_record=False)
            coh_tf = np.asarray(m["coh_tf"], dtype=float)
            freqs_coh = np.asarray(m["freqs_coh"], dtype=float).reshape(-1)
            times_coh = np.asarray(m["time_coh"], dtype=float).reshape(-1)
            freqs_gc = np.asarray(m["freqs_gc"], dtype=float).reshape(-1)
            gc_a = np.asarray(m["gc_a2h"], dtype=float).reshape(-1)
            gc_h = np.asarray(m["gc_h2a"], dtype=float).reshape(-1)

            if ref_freqs_coh is None:
                ref_freqs_coh = freqs_coh
                ref_times_coh = times_coh
                ref_freqs_gc = freqs_gc

            coh_list.append(_interp_coh_to_ref(coh_tf, freqs_coh, times_coh, ref_freqs_coh, ref_times_coh))
            a_list.append(_interp_1d_to_ref(freqs_gc, gc_a, ref_freqs_gc))
            h_list.append(_interp_1d_to_ref(freqs_gc, gc_h, ref_freqs_gc))
            used_files.append(p.name)
        except Exception:
            skipped_files.append(p.name)

    if not coh_list or ref_freqs_coh is None or ref_times_coh is None or ref_freqs_gc is None:
        raise RuntimeError(f"No readable subject full-spectrum .mat files found under {out_dir}")

    return (
        candidates,
        skipped_files,
        np.asarray(used_files, dtype=object),
        np.stack(coh_list, axis=0),
        np.stack(a_list, axis=0),
        np.stack(h_list, axis=0),
        np.array([ref_freqs_coh, ref_times_coh, ref_freqs_gc], dtype=object),
    )


def summarize_full_spectrum_group(
    out_dir: Path,
    mats: list[Path] | None = None,
    skipped_runs: list[str] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    _, skipped_files, used_files_arr, coh_stack, a_stack, h_stack, refs = _load_subject_mats(out_dir, mats)
    if skipped_runs:
        skipped_files = [*skipped_files, *skipped_runs]
    ref_freqs_coh = np.asarray(refs[0], dtype=float)
    ref_times_coh = np.asarray(refs[1], dtype=float)
    ref_freqs_gc = np.asarray(refs[2], dtype=float)

    group_coh = np.nanmean(coh_stack, axis=0)
    group_gc_a = np.nanmean(a_stack, axis=0)
    group_gc_h = np.nanmean(h_stack, axis=0)
    gc_a_sem = np.nanstd(a_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(a_stack), axis=0), 1))
    gc_h_sem = np.nanstd(h_stack, axis=0, ddof=0) / np.sqrt(np.maximum(np.sum(np.isfinite(h_stack), axis=0), 1))

    pvals = np.full(len(ref_freqs_gc), np.nan, dtype=float)
    n_pairs = np.zeros(len(ref_freqs_gc), dtype=int)
    for fi in range(len(ref_freqs_gc)):
        a = a_stack[:, fi]
        h = h_stack[:, fi]
        ok = np.isfinite(a) & np.isfinite(h)
        n_pairs[fi] = int(np.sum(ok))
        if n_pairs[fi] < 3:
            continue
        _, pvals[fi] = ttest_rel(a[ok], h[ok], nan_policy="omit")

    sig_mask_fdr = _fdr_bh(pvals, alpha=0.05)
    perm_thr_a, perm_p_a = _perm_upper_threshold(a_stack, quantile=0.999, n_perm=10000, seed=42)
    perm_thr_h, perm_p_h = _perm_upper_threshold(h_stack, quantile=0.999, n_perm=10000, seed=43)
    perm_sig_a = np.isfinite(perm_p_a) & (perm_p_a < 0.001)
    perm_sig_h = np.isfinite(perm_p_h) & (perm_p_h < 0.001)
    sig_spans = _mask_to_spans(sig_mask_fdr, ref_freqs_gc)
    used_files = [str(x) for x in used_files_arr.tolist()] if used_files_arr.size else []

    # Plot 1: group coherence heatmap
    fig1, ax1 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    extent = [float(ref_times_coh.min()), float(ref_times_coh.max()), float(ref_freqs_coh.min()), float(ref_freqs_coh.max())]
    im = ax1.imshow(group_coh, aspect='auto', origin='lower', extent=extent, cmap='viridis')
    ax1.set_title('Group Full-Spectrum Coherence (A-H)')
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Frequency (Hz)')
    fig1.colorbar(im, ax=ax1, label='Coherence')
    fig1.tight_layout()
    coh_png = out_dir / 'group_fullspectrum_coherence.png'
    fig1.savefig(coh_png)
    plt.close(fig1)

    # Plot 2: group sGC line chart
    fig2, ax2 = plt.subplots(figsize=(7.2, 4.8), dpi=220)
    ax2.plot(ref_freqs_gc, group_gc_a, color='#4d4d4d', lw=2.2, label='A→H')
    ax2.fill_between(ref_freqs_gc, group_gc_a - gc_a_sem, group_gc_a + gc_a_sem, color='#4d4d4d', alpha=0.2)
    ax2.plot(ref_freqs_gc, perm_thr_a, color='#4d4d4d', lw=1.2, ls='--', alpha=0.9, label='A→H perm 99.9%')
    ax2.plot(ref_freqs_gc, group_gc_h, color='#2f6fbd', lw=2.2, label='H→A')
    ax2.fill_between(ref_freqs_gc, group_gc_h - gc_h_sem, group_gc_h + gc_h_sem, color='#2f6fbd', alpha=0.2)
    ax2.plot(ref_freqs_gc, perm_thr_h, color='#2f6fbd', lw=1.2, ls='--', alpha=0.9, label='H→A perm 99.9%')
    # for lo, hi in sig_spans:
    #     ax2.axvspan(lo, hi, color='#ef476f', alpha=0.18, lw=0)
    ax2.set_title('Group Full-Spectrum Spectral GC')
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Granger index')
    ax2.set_xlim(2, 45)
    ax2.grid(alpha=0.25)
    ax2.legend(frameon=False)
    if sig_spans:
        ax2.text(0.02, 0.97, 'Shaded: A→H vs H→A, paired t-test FDR q<0.05', transform=ax2.transAxes, va='top', fontsize=8)
    else:
        ax2.text(0.02, 0.97, 'No frequency survived FDR q<0.05', transform=ax2.transAxes, va='top', fontsize=8)
    fig2.tight_layout()
    gc_png = out_dir / 'group_fullspectrum_sgc.png'
    fig2.savefig(gc_png)
    plt.close(fig2)

    # Plot 3: literature-style combined panel
    fig3 = plt.figure(figsize=(14.0, 5.2), dpi=220)
    gs = fig3.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.6, left=0.08, right=0.95, bottom=0.15, top=0.78)

    axc = fig3.add_subplot(gs[0, 0])
    im2 = axc.imshow(group_coh, aspect='auto', origin='lower', extent=extent, cmap='viridis', interpolation='gaussian')
    axc.set_title('A  Coherence (A-H)', loc='left', fontsize=13, fontweight='bold', pad=25)
    axc.set_xlabel('Time (s)')
    axc.set_ylabel('Frequency (Hz)')
    fig3.colorbar(im2, ax=axc, fraction=0.046, pad=0.04, label='Coherence')

    axa = fig3.add_subplot(gs[0, 1])
    axa.plot(ref_freqs_gc, group_gc_a, color='#4d4d4d', lw=2.0)
    axa.fill_between(ref_freqs_gc, group_gc_a - gc_a_sem, group_gc_a + gc_a_sem, color='#4d4d4d', alpha=0.2)
    axa.plot(ref_freqs_gc, perm_thr_a, color='#4d4d4d', lw=1.1, ls='--', alpha=0.9)
    # for lo, hi in sig_spans:
    #     axa.axvspan(lo, hi, color='#ef476f', alpha=0.18, lw=0)
    axa.set_title('B  Spectral Granger Causality\nA→H', loc='left', fontsize=13, fontweight='bold', pad=25)
    axa.set_xlabel('Frequency (Hz)')
    axa.set_ylabel('Granger index')
    axa.set_xlim(2, 45)
    axa.grid(alpha=0.25)

    axh = fig3.add_subplot(gs[0, 2])
    axh.plot(ref_freqs_gc, group_gc_h, color='#2f6fbd', lw=2.0)
    axh.fill_between(ref_freqs_gc, group_gc_h - gc_h_sem, group_gc_h + gc_h_sem, color='#2f6fbd', alpha=0.2)
    axh.plot(ref_freqs_gc, perm_thr_h, color='#2f6fbd', lw=1.1, ls='--', alpha=0.9)
    # for lo, hi in sig_spans:
    #     axh.axvspan(lo, hi, color='#ef476f', alpha=0.18, lw=0)
    axh.set_title('H→A', fontsize=12, fontweight='bold')
    axh.set_xlabel('Frequency (Hz)')
    axh.set_xlim(2, 45)
    axh.grid(alpha=0.25)

    fig3.suptitle(f'Group full-spectrum connectivity (n={len(used_files)} runs)', fontsize=11, y=0.98)
    # fig3.tight_layout(rect=[0, 0, 1, 0.96]) # Tight layout often ignores wspace in gridspec
    combo_png = out_dir / 'group_fullspectrum_literature_style.png'
    group_mat = out_dir / 'group_fullspectrum_connectivity.mat'
    fig3.savefig(combo_png, bbox_inches='tight')
    plt.close(fig3)

    summary_txt = out_dir / 'group_fullspectrum_summary.txt'
    with summary_txt.open('w', encoding='utf-8') as f:
        f.write(f'total_mat_files={len(used_files) + len(skipped_files)}\n')
        f.write(f'used_runs={len(used_files)}\n')
        f.write(f'skipped_runs={len(skipped_files)}\n')
        if skipped_files:
            f.write('skipped_list=\n')
            for name in skipped_files:
                f.write(f'  {name}\n')
        f.write(f'sig_bins_fdr_q05={int(np.sum(sig_mask_fdr))}\n')
        if sig_spans:
            f.write('sig_spans_hz=\n')
            for lo, hi in sig_spans:
                f.write(f'  {lo:.3f}-{hi:.3f}\n')
        else:
            f.write('sig_spans_hz=none\n')
        f.write(f'perm_sig_bins_a2h_p_lt_0.001={int(np.sum(perm_sig_a))}\n')
        f.write(f'perm_sig_bins_h2a_p_lt_0.001={int(np.sum(perm_sig_h))}\n')

    savemat(
        group_mat,
        {
            'used_files': np.array(used_files, dtype=object),
            'skipped_files': np.array(skipped_files, dtype=object),
            'freqs_coh': ref_freqs_coh,
            'time_coh': ref_times_coh,
            'group_coh_tf': group_coh,
            'freqs_gc': ref_freqs_gc,
            'group_gc_a2h': group_gc_a,
            'group_gc_h2a': group_gc_h,
            'group_gc_a2h_sem': gc_a_sem,
            'group_gc_h2a_sem': gc_h_sem,
            'sgc_pvals': pvals,
            'sgc_sig_mask_fdr_q05': sig_mask_fdr.astype(np.uint8),
            'sgc_n_pairs_per_freq': n_pairs,
            'perm_thr_a2h_q999': perm_thr_a,
            'perm_thr_h2a_q999': perm_thr_h,
            'group_gc_a2h_cl_perm_q999': perm_thr_a,
            'group_gc_h2a_cl_perm_q999': perm_thr_h,
            'perm_pvals_a2h': perm_p_a,
            'perm_pvals_h2a': perm_p_h,
            'perm_sig_mask_a2h_p_lt_0p001': perm_sig_a.astype(np.uint8),
            'perm_sig_mask_h2a_p_lt_0p001': perm_sig_h.astype(np.uint8),
        },
        do_compression=True,
    )

    sig_png = out_dir / 'group_fullspectrum_sgc_significance.png'
    fig4, ax4 = plt.subplots(figsize=(7.2, 3.0), dpi=220)
    ax4.plot(ref_freqs_gc, pvals, color='#555555', lw=1.5, label='p-value')
    ax4.axhline(0.05, color='#888888', ls='--', lw=1.0, label='0.05')
    for lo, hi in sig_spans:
        ax4.axvspan(lo, hi, color='#ef476f', alpha=0.18, lw=0)
    ax4.set_yscale('log')
    ax4.set_ylim(1e-6, 1)
    ax4.set_xlim(2, 45)
    ax4.set_xlabel('Frequency (Hz)')
    ax4.set_ylabel('paired p-value (log)')
    ax4.set_title('A→H vs H→A significance by frequency (FDR q<0.05 shaded)')
    ax4.grid(alpha=0.25)
    ax4.legend(frameon=False)
    fig4.tight_layout()
    fig4.savefig(sig_png)
    plt.close(fig4)

    print(f'used_runs={len(used_files)} skipped_runs={len(skipped_files)}')
    print(f'saved {coh_png}')
    print(f'saved {gc_png}')
    print(f'saved {sig_png}')
    print(f'saved {combo_png}')
    print(f'saved {group_mat}')
    print(f'saved {summary_txt}')


def main() -> None:
    summarize_full_spectrum_group(Path('/Volumes/rmhyw/keles_ah_nwb_pipeline/results/full_spectrum_batch'))


if __name__ == '__main__':
    main()
