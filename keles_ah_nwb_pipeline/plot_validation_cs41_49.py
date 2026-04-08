from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main() -> None:
    out = Path('/Volumes/rmhyw/keles_ah_nwb_pipeline/results/connectivity_only')

    coh_files = [
        p
        for p in out.glob('*_AH_coherence.csv')
        if not p.name.startswith('all_subjects_') and not p.name.startswith('._') and p.stat().st_size > 100
    ]
    sgc_files = [
        p
        for p in out.glob('*_sGC.csv')
        if not p.name.startswith('all_subjects_') and not p.name.startswith('._') and p.stat().st_size > 100
    ]

    pat = re.compile(r'sub-cs(\d+)_', re.I)
    coh_files = [p for p in coh_files if (m := pat.search(p.name)) and 41 <= int(m.group(1)) <= 49]
    sgc_files = [p for p in sgc_files if (m := pat.search(p.name)) and 41 <= int(m.group(1)) <= 49]

    coh_frames = []
    for path in sorted(coh_files):
        frame = pd.read_csv(path)
        frame['run_id'] = path.stem.replace('_AH_coherence', '')
        coh_frames.append(frame)

    sgc_frames = []
    for path in sorted(sgc_files):
        frame = pd.read_csv(path)
        frame['run_id'] = path.stem.replace('_sGC', '')
        sgc_frames.append(frame)

    if not coh_frames or not sgc_frames:
        raise RuntimeError('No valid cs41-49 files to plot')

    coh = pd.concat(coh_frames, ignore_index=True)
    sgc = pd.concat(sgc_frames, ignore_index=True)

    summary = {
        'coh_runs': int(coh['run_id'].nunique()),
        'coh_subjects': int(coh['subject'].nunique()) if 'subject' in coh.columns else 0,
        'coh_rows': int(len(coh)),
        'sgc_runs': int(sgc['run_id'].nunique()),
        'sgc_subjects': int(sgc['subject'].nunique()) if 'subject' in sgc.columns else 0,
        'sgc_rows': int(len(sgc)),
        'sgc_valid_ratio': float(np.mean(np.isfinite(sgc['A_to_H_gc']) & np.isfinite(sgc['H_to_A_gc']))),
    }
    pd.DataFrame([summary]).to_csv(out / 'validation_cs41_49_summary.csv', index=False)

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=180)
    bands = ['theta', 'beta']
    values = [coh.loc[coh['band'].str.lower() == band, 'A_H_coherence'].dropna().to_numpy() for band in bands]
    ax.boxplot(values, tick_labels=bands, showfliers=False)
    for idx, arr in enumerate(values, start=1):
        if len(arr) == 0:
            continue
        sample_n = min(1500, len(arr))
        sample = np.random.choice(arr, size=sample_n, replace=False)
        jitter = np.random.uniform(-0.15, 0.15, size=sample_n)
        ax.scatter(np.full(sample_n, idx) + jitter, sample, s=2, alpha=0.2)
    ax.set_ylabel('A-H Coherence')
    ax.set_title('Validation (cs41-49): coherence by band')
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / 'validation_cs41_49_coherence_band.png')
    plt.close(fig)

    sgc_valid = sgc[np.isfinite(sgc['A_to_H_gc']) & np.isfinite(sgc['H_to_A_gc'])].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=180)
    if len(sgc_valid) > 0:
        a_to_h = np.log1p(sgc_valid['A_to_H_gc'].to_numpy())
        h_to_a = np.log1p(sgc_valid['H_to_A_gc'].to_numpy())
        ax.hist(a_to_h, bins=60, alpha=0.45, label='log1p(A→H)', density=True)
        ax.hist(h_to_a, bins=60, alpha=0.45, label='log1p(H→A)', density=True)
    ax.set_title('Validation (cs41-49): sGC direction distributions')
    ax.set_xlabel('log1p(Granger F)')
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / 'validation_cs41_49_sgc_direction_hist.png')
    plt.close(fig)

    run_coh = coh.groupby(['run_id', 'band'], as_index=False)['A_H_coherence'].mean()
    run_sgc = (
        sgc.assign(valid=np.isfinite(sgc['A_to_H_gc']) & np.isfinite(sgc['H_to_A_gc']))
        .groupby('run_id', as_index=False)['valid']
        .mean()
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), dpi=180)
    for band, color in [('theta', '#4e79a7'), ('beta', '#f28e2b')]:
        frame = run_coh[run_coh['band'].str.lower() == band].sort_values('A_H_coherence')
        axes[0].barh(frame['run_id'], frame['A_H_coherence'], alpha=0.8, label=band, color=color)
    axes[0].set_title('Run mean coherence')
    axes[0].set_xlabel('mean A-H coherence')
    axes[0].legend(frameon=False)
    axes[0].grid(axis='x', alpha=0.2)

    frame2 = run_sgc.sort_values('valid')
    axes[1].barh(frame2['run_id'], frame2['valid'], color='#59a14f', alpha=0.85)
    axes[1].set_xlim(0, 1)
    axes[1].set_title('Run valid sGC ratio')
    axes[1].set_xlabel('fraction finite (A→H and H→A)')
    axes[1].grid(axis='x', alpha=0.2)

    fig.tight_layout()
    fig.savefig(out / 'validation_cs41_49_run_qc.png')
    plt.close(fig)

    print(summary)
    print('saved', out / 'validation_cs41_49_coherence_band.png')
    print('saved', out / 'validation_cs41_49_sgc_direction_hist.png')
    print('saved', out / 'validation_cs41_49_run_qc.png')
    print('saved', out / 'validation_cs41_49_summary.csv')


if __name__ == '__main__':
    main()
