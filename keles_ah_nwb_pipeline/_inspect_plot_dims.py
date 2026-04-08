from pathlib import Path
import pandas as pd
import re

out = Path('/Volumes/rmhyw/keles_ah_nwb_pipeline/results/connectivity_only')
pat = re.compile(r'sub-cs(\d+)_', re.I)
coh = []
sgc = []
for p in out.glob('*_AH_coherence.csv'):
    if p.name.startswith('._') or p.name.startswith('all_subjects_') or p.stat().st_size <= 100:
        continue
    m = pat.search(p.name)
    if m and 41 <= int(m.group(1)) <= 49:
        coh.append(pd.read_csv(p, usecols=['band', 'valence', 'A_H_coherence']))

for p in out.glob('*_sGC.csv'):
    if p.name.startswith('._') or p.name.startswith('all_subjects_') or p.stat().st_size <= 100:
        continue
    m = pat.search(p.name)
    if m and 41 <= int(m.group(1)) <= 49:
        sgc.append(pd.read_csv(p, usecols=['band', 'valence', 'A_to_H_gc', 'H_to_A_gc']))

coh_df = pd.concat(coh, ignore_index=True)
sgc_df = pd.concat(sgc, ignore_index=True)
print('coh bands', sorted(coh_df['band'].dropna().astype(str).str.lower().unique()))
print('coh valence', sorted(coh_df['valence'].dropna().astype(str).str.lower().unique()))
print('sgc bands', sorted(sgc_df['band'].dropna().astype(str).str.lower().unique()))
print('sgc valence', sorted(sgc_df['valence'].dropna().astype(str).str.lower().unique()))
