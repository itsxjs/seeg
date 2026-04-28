import scipy.io as sio
import numpy as np

paths = [
    "/Volumes/rmhyw/姜芳丽rate/sub008_ratingmatrix.mat",
    "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/sub001_ratingmatrix.mat"
]

for p in paths:
    print(f"\n--- {p} ---")
    try:
        data = sio.loadmat(p)
        for k in data.keys():
            if not k.startswith('__'):
                val = data[k]
                print(f"Key: {k}, Shape: {val.shape}")
                if val.ndim > 0:
                    print(f"Data slice:\n{val[:5]}")
    except Exception as e:
        print(f"Error: {e}")
