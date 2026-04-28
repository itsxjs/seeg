import h5py
import numpy as np

p = "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330_spike.mat"
with h5py.File(p, 'r') as f:
    print(f"Keys: {list(f.keys())}")
    if 'spike_Tps' in f:
        refs = f['spike_Tps'][0]
        ref = refs[0]
        st = f[ref][:]
        print(f"Unit 0 spike times shape: {st.shape}, example: {st.flatten()[:5]}")
        print(f"Min: {np.min(st)}, Max: {np.max(st)}")
