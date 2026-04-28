import h5py
import numpy as np

p = "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat"
with h5py.File(p, 'r') as f:
    spike_tps_refs = f['spike_Tps'][0]
    print(f"Number of units: {len(spike_tps_refs)}")
    for i in range(min(3, len(spike_tps_refs))):
        ref = spike_tps_refs[i]
        data = f[ref][:]
        print(f"Unit {i} spike times shape: {data.shape}, example: {data.flatten()[:5]}")

    # Check for another key that might be trial/event related
    print(f"Other keys: {list(f.keys())}")
