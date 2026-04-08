import numpy as np
from scipy.io import loadmat

p = '/Volumes/rmhyw/keles_ah_nwb_pipeline/results/full_spectrum_batch/group_fullspectrum_connectivity.mat'
m = loadmat(p, squeeze_me=True, struct_as_record=False)
f = np.asarray(m['freqs_gc']).reshape(-1)
a = np.asarray(m['group_gc_a2h']).reshape(-1)
h = np.asarray(m['group_gc_h2a']).reshape(-1)
sig = np.asarray(m['sgc_sig_mask_fdr_q05']).reshape(-1).astype(bool)

d = a - h
print('sig_bins', int(sig.sum()))
print('sig A>H bins', int(np.sum(sig & (d > 0))))
print('sig H>A bins', int(np.sum(sig & (d < 0))))

start = None
for i, v in enumerate(sig):
    if v and start is None:
        start = i
    if (not v or i == len(sig) - 1) and start is not None:
        end = i if (v and i == len(sig) - 1) else i - 1
        md = float(np.nanmean(d[start:end + 1]))
        direction = 'A->H' if md > 0 else 'H->A'
        print(f'{f[start]:.3f}-{f[end]:.3f} Hz | mean(A-H)={md:.6f} | {direction} stronger')
        start = None

print('global mean A', float(np.nanmean(a)))
print('global mean H', float(np.nanmean(h)))
print('global mean A-H', float(np.nanmean(d)))
