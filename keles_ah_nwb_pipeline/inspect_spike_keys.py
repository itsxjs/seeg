import h5py
import numpy as np

p = "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat"
with h5py.File(p, 'r') as f:
    for k in ['spike_Tps', 'spikes']:
        obj = f[k]
        print(f"Key: {k}, Shape: {obj.shape}, Type: {type(obj)}")
        if isinstance(obj, h5py.Dataset):
            data = obj[:]
            print(f"  Data extract: {data.flatten()[:5]}")
        elif isinstance(obj, h5py.Group):
            print(f"  Group keys: {list(obj.keys())[:5]}")
