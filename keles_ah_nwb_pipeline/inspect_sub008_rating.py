import h5py
import numpy as np
import scipy.io as sio

p_jiang = "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_1.mat"
print(f"--- Checking {p_jiang} ---")
try:
    with h5py.File(p_jiang, 'r') as f:
        print(list(f.keys()))
        if 'ratingmatrix' in f:
            print(f"ratingmatrix shape: {f['ratingmatrix'].shape}")
except:
    try:
        data = sio.loadmat(p_jiang)
        print(data.keys())
    except:
        print("Failed to load")

p_shan = "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330.mat"
print(f"\n--- Checking {p_shan} ---")
try:
    with h5py.File(p_shan, 'r') as f:
        print(list(f.keys()))
except:
    print("Failed")
