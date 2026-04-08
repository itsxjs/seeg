import numpy as np
from scipy.io import loadmat

p = '/Volumes/rmhyw/keles_ah_nwb_pipeline/results/full_spectrum_batch/group_fullspectrum_connectivity.mat'
m = loadmat(p, squeeze_me=True, struct_as_record=False)
f = np.asarray(m['freqs_coh']).reshape(-1)
t = np.asarray(m['time_coh']).reshape(-1)
coh = np.asarray(m['group_coh_tf'])

# global peak
idx = np.unravel_index(np.nanargmax(coh), coh.shape)
print('global_peak_coh', float(coh[idx]))
print('global_peak_freq_hz', float(f[idx[0]]))
print('global_peak_time_s', float(t[idx[1]]))

# freq profile and top bands
freq_mean = np.nanmean(coh, axis=1)
order = np.argsort(freq_mean)[::-1]
print('top5_freq_by_mean_coh:')
for i in order[:5]:
    print(f'  {f[i]:.3f} Hz -> {freq_mean[i]:.6f}')

# coarse canonical bands
bands = {
    'theta': (4, 8),
    'alpha': (8, 13),
    'beta': (13, 30),
    'low_gamma': (30, 45),
}
for name, (lo, hi) in bands.items():
    mask = (f >= lo) & (f <= hi)
    if np.any(mask):
        print(f'{name}_mean_coh', float(np.nanmean(coh[mask, :])))
