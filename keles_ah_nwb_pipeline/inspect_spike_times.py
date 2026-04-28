import h5py
import numpy as np

p = "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat"
with h5py.File(p, 'r') as f:
    refs = f['spike_Tps'][0]
    # Look for a unit that has a reasonable number of spikes (e.g. > 1000)
    for i, ref in enumerate(refs):
        st = f[ref][:]
        if st.size > 1000:
            print(f"Unit {i} spike times shape: {st.shape}")
            print(f"First 10 spike times: {st.flatten()[:10]}")
            print(f"Min: {np.min(st)}, Max: {np.max(st)}")
            diffs = np.diff(st.flatten())
            print(f"Median ISI: {np.median(diffs)}")
            break
