import scipy.io as sio
import numpy as np

paths = [
    "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330_spike.mat",
    "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat"
]

for p in paths:
    print(f"\n--- {p} ---")
    try:
        data = sio.loadmat(p)
        for k in data.keys():
            if not k.startswith('__'):
                val = data[k]
                shape = val.shape if hasattr(val, 'shape') else 'N/A'
                print(f"Key: {k}, Shape: {shape}, Type: {type(val)}")
                if isinstance(val, np.ndarray) and val.size > 0:
                    print(f"  Example: {val[0] if val.ndim > 0 else val}")
    except Exception as e:
        print(f"Error loading {p}: {e}")
