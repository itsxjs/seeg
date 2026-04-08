from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.stats import mannwhitneyu

BASE = Path('/Volumes/rmhyw/keles_ah_nwb_pipeline/results/spike_region_batch_000623/timecurve_clusters')
UNIT_TABLE = BASE / 'unit_timecurve_cluster_table.csv'


def region_from_text(text: str) -> str:
    t = str(text).lower()
    if ('amyg' in t) or ('amygdala' in t):
        return 'A'
    if ('hipp' in t) or ('hippocampus' in t) or ('hc' in t):
        return 'H'
    return 'Other'


def map_unit_region(nwb_path: str, unit_index: int) -> str:
    p = Path(nwb_path)
    with NWBHDF5IO(str(p), mode='r', load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            return 'Unknown'
        u = nwb.units.to_dataframe().reset_index(drop=True)
        if 'electrodes' not in u.columns:
            return 'Unknown'
        if unit_index < 0 or unit_index >= len(u):
            return 'Unknown'
        elec = u.iloc[unit_index]['electrodes']
        if hasattr(elec, 'get'):
            locs = elec.get('location', pd.Series([], dtype=str)).astype(str).tolist()
        else:
            locs = []
        tags = {region_from_text(x) for x in locs}
        if 'A' in tags and 'H' not in tags:
            return 'A'
        if 'H' in tags and 'A' not in tags:
            return 'H'
        if 'A' in tags and 'H' in tags:
            return 'A+H'
        return 'Other'


def main() -> None:
    df = pd.read_csv(UNIT_TABLE)

    # cache by file for speed
    cache: dict[tuple[str, int], str] = {}
    for nwb_path, g in df.groupby('nwb_file'):
        p = Path(nwb_path)
        try:
            with NWBHDF5IO(str(p), mode='r', load_namespaces=True) as io:
                nwb = io.read()
                if nwb.units is None:
                    continue
                u = nwb.units.to_dataframe().reset_index(drop=True)
                if 'electrodes' not in u.columns:
                    continue
                for idx in g['unit_index'].astype(int).unique():
                    if idx < 0 or idx >= len(u):
                        continue
                    elec = u.iloc[idx]['electrodes']
                    if hasattr(elec, 'get'):
                        locs = elec.get('location', pd.Series([], dtype=str)).astype(str).tolist()
                    else:
                        locs = []
                    tags = {region_from_text(x) for x in locs}
                    if 'A' in tags and 'H' not in tags:
                        reg = 'A'
                    elif 'H' in tags and 'A' not in tags:
                        reg = 'H'
                    elif 'A' in tags and 'H' in tags:
                        reg = 'A+H'
                    else:
                        reg = 'Other'
                    cache[(nwb_path, int(idx))] = reg
        except Exception:
            continue

    df['region'] = [cache.get((r.nwb_file, int(r.unit_index)), 'Unknown') for _, r in df.iterrows()]

    ct = pd.crosstab(df['region'], df['cluster'])
    ct_prop = ct.div(ct.sum(axis=1), axis=0)

    print('overall_region_cluster_counts')
    print(ct.to_string())
    print('\noverall_region_cluster_row_prop')
    print(ct_prop.round(3).to_string())

    sub = df.groupby('subject').agg(
        n_units=('cluster', 'size'),
        c1_frac=('cluster', lambda s: float(np.mean(s == 1))),
    )
    print('\nsubject_cluster_fraction_highest_c1')
    print(sub.sort_values('c1_frac', ascending=False).head(8).round(3).to_string())
    print('\nsubject_cluster_fraction_lowest_c1')
    print(sub.sort_values('c1_frac', ascending=True).head(8).round(3).to_string())

    ah = df[df['region'].isin(['A', 'H'])].copy()
    if len(ah):
        A = ah.loc[ah['region'] == 'A', 'cluster'].to_numpy()
        H = ah.loc[ah['region'] == 'H', 'cluster'].to_numpy()
        if len(A) > 5 and len(H) > 5:
            _, p = mannwhitneyu(A, H, alternative='two-sided')
            print('\nA_vs_H_cluster_label_test')
            print('p_value', float(p))
            print('A_c1_frac', float(np.mean(A == 1)))
            print('H_c1_frac', float(np.mean(H == 1)))

        ah_sub = ah.groupby(['subject', 'region']).agg(
            n=('cluster', 'size'),
            c1_frac=('cluster', lambda s: float(np.mean(s == 1))),
        ).reset_index()
        piv = ah_sub.pivot(index='subject', columns='region', values='c1_frac')
        piv['A_minus_H_c1'] = piv.get('A', np.nan) - piv.get('H', np.nan)
        print('\nA_minus_H_c1_top')
        print(piv.sort_values('A_minus_H_c1', ascending=False).head(8).round(3).to_string())
        print('\nA_minus_H_c1_bottom')
        print(piv.sort_values('A_minus_H_c1', ascending=True).head(8).round(3).to_string())

    out = BASE / 'unit_timecurve_cluster_table_with_region.csv'
    df.to_csv(out, index=False)
    print('\nsaved', out)


if __name__ == '__main__':
    main()
