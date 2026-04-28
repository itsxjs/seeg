import h5py
import numpy as np

paths = [
    "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330_spike.mat",
    "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat"
]

def print_h5_structure(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(f"Dataset: {name}, Shape: {obj.shape}, Type: {obj.dtype}")
    elif isinstance(obj, h5py.Group):
        print(f"Group: {name}")

for p in paths:
    print(f"\n--- {p} ---")
    try:
        with h5py.File(p, 'r') as f:
            f.visititems(print_h5_structure)
    except Exception as e:
        print(f"Error loading {p}: {e}")
