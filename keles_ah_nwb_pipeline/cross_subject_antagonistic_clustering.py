import h5py
import numpy as np
import scipy.io as sio
import pandas as pd
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from scipy import stats
from sklearn.cluster import KMeans

# Configuration
FS = 30000.0  
BIN_SIZE = 0.05  # 50ms for smoother resolution
SMOOTH_SIGMA = 2.0 # ~100ms smoothing width
T_MIN = -0.5
T_MAX = 2.0
BINS = np.arange(T_MIN, T_MAX + BIN_SIZE, BIN_SIZE)
BIN_CENTERS = BINS[:-1] + BIN_SIZE/2
BASELINE_START = -0.5
BASELINE_END = 0.0
SIG_START = 0.0

SUBJECTS = {
    "sub001_Shan": {
        "spike_mat": "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330_spike.mat",
        "rating_mat": "/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/sub001_ratingmatrix.mat"
    },
    "sub008_Jiang": {
        "spike_mat": "/Volumes/rmhyw/姜芳丽spike_rate/tiktok3-20250908-1504_spike.mat",
        "rating_mat": "/Volumes/rmhyw/姜芳丽rate/sub008_ratingmatrix.mat"
    }
}


def fdr_bh(pvals, alpha=0.05):
    pvals = np.asarray(pvals)
    m = pvals.size
    order = np.argsort(pvals)
    ranked = pvals[order]
    thresh = alpha * np.arange(1, m + 1) / m
    passed = ranked <= thresh

    sig = np.zeros(m, dtype=bool)
    if np.any(passed):
        k = np.where(passed)[0].max()
        cutoff = ranked[k]
        sig = pvals <= cutoff
    return sig


def contiguous_sig_windows(sig_mask, bin_centers, bin_size, min_bins=2):
    windows = []
    start = None
    for i, is_sig in enumerate(sig_mask):
        if is_sig and start is None:
            start = i
        elif (not is_sig) and (start is not None):
            end = i - 1
            if (end - start + 1) >= min_bins:
                windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
            start = None
    if start is not None:
        end = len(sig_mask) - 1
        if (end - start + 1) >= min_bins:
            windows.append((bin_centers[start] - bin_size / 2, bin_centers[end] + bin_size / 2))
    return windows


def baseline_correct(curve):
    base_idx = (BIN_CENTERS >= BASELINE_START) & (BIN_CENTERS < BASELINE_END)
    if not np.any(base_idx):
        return curve
    return curve - np.mean(curve[base_idx])

def load_data(sub_id, config):
    print(f"Processing {sub_id}...")
    rat_data = sio.loadmat(config["rating_mat"])["ratingmatrix"]
    labels = rat_data[:, 4]
    onsets = rat_data[:, 5] * FS 
    
    like_onsets = onsets[(labels == 4) | (labels == 5)]
    dislike_onsets = onsets[(labels == 1) | (labels == 2)]
    print(f"  Like trials: {len(like_onsets)}, Dislike trials: {len(dislike_onsets)}")
    
    spike_features = []
    unit_ids = []
    
    with h5py.File(config["spike_mat"], 'r') as f:
        refs = f['spike_Tps'][0]
        for i, ref in enumerate(refs):
            st = f[ref][:].flatten()
            if st.size < 50: continue 
            
            def get_ifr(trial_onsets):
                all_trials = []
                for onset in trial_onsets:
                    rel = (st - onset) / FS
                    counts, _ = np.histogram(rel, bins=BINS)
                    all_trials.append(counts / BIN_SIZE)
                if not all_trials: return np.zeros(len(BINS)-1)
                curve = np.mean(all_trials, axis=0)
                # Apply Gaussian smoothing to replicate Keles style
                return gaussian_filter1d(curve, sigma=SMOOTH_SIGMA)

            ifr_like = baseline_correct(get_ifr(like_onsets))
            ifr_dislike = baseline_correct(get_ifr(dislike_onsets))
            
            diff = ifr_like - ifr_dislike
            if np.max(np.abs(diff)) > 0.01: 
                # Normalize peak to 1/-1 for clustering pattern comparison
                diff_norm = diff / (np.max(np.abs(diff)) + 1e-6)
                spike_features.append(diff_norm)
                unit_ids.append(f"{sub_id}_u{i}")
                
    if not spike_features:
        return np.empty((0, len(BINS)-1)), []
    return np.array(spike_features), unit_ids

def analyze():
    all_features = []
    all_meta = []
    
    for sub, config in SUBJECTS.items():
        feat, ids = load_data(sub, config)
        if feat.size > 0:
            all_features.append(feat)
            all_meta.extend(ids)
    
    X = np.vstack(all_features)
    print(f"Clustering {X.shape[0]} total units...")
    
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X)
    
    plt.figure(figsize=(10, 6))
    colors = ['#1f77b4', '#d62728']
    
    for c in [0, 1]:
        Xc = X[clusters == c]
        mean_curve = np.mean(Xc, axis=0)
        # Identify polarity for labeling
        peak_idx = np.argmax(np.abs(mean_curve))
        label_suffix = "Like Preference" if mean_curve[peak_idx] > 0 else "Dislike Preference"
        
        sem_curve = np.std(Xc, axis=0) / np.sqrt(len(Xc))
        plt.plot(BIN_CENTERS, mean_curve, color=colors[c], label=f"Cluster {c}: {label_suffix} (n={len(Xc)})")
        plt.fill_between(BIN_CENTERS, mean_curve - sem_curve, mean_curve + sem_curve, color=colors[c], alpha=0.15)
        
    plt.axvline(0, color='black', linestyle='--', alpha=0.8, label='Onset')
    plt.axhline(0, color='black', linestyle='-', linewidth=0.5)
    plt.title("Antagonistic Neuron Clusters (Smoothed Style)")
    plt.xlabel("Time from onset (s)")
    plt.ylabel("Mean Normalized Difference (Like - Dislike)")
    plt.legend(frameon=False)
    plt.grid(True, alpha=0.15)
    
    out_pth = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results/antagonistic_clusters_like_dislike_smoothed.png"
    plt.savefig(out_pth, dpi=200)
    plt.close()

    # Significant windows between clusters (independent-unit comparison across bins)
    x0 = X[clusters == 0]
    x1 = X[clusters == 1]
    _, pvals = stats.ttest_ind(x0, x1, axis=0, equal_var=False, nan_policy='omit')
    sig_mask = fdr_bh(pvals, alpha=0.05)
    sig_mask = sig_mask & (BIN_CENTERS >= SIG_START)
    sig_windows = contiguous_sig_windows(sig_mask, BIN_CENTERS, BIN_SIZE, min_bins=2)

    plt.figure(figsize=(10, 6))
    colors = ['#1f77b4', '#d62728']
    for c in [0, 1]:
        Xc = X[clusters == c]
        mean_curve = np.mean(Xc, axis=0)
        sem_curve = np.std(Xc, axis=0, ddof=1) / np.sqrt(len(Xc)) if len(Xc) > 1 else np.zeros_like(mean_curve)
        peak_idx = np.argmax(np.abs(mean_curve))
        label_suffix = "Like Preference" if mean_curve[peak_idx] > 0 else "Dislike Preference"
        plt.plot(BIN_CENTERS, mean_curve, color=colors[c], label=f"Cluster {c}: {label_suffix} (n={len(Xc)})")
        plt.fill_between(BIN_CENTERS, mean_curve - sem_curve, mean_curve + sem_curve, color=colors[c], alpha=0.12)

    for i, (t0, t1) in enumerate(sig_windows):
        lbl = 'FDR<0.05 (>=2 bins)' if i == 0 else None
        plt.axvspan(t0, t1, color='gold', alpha=0.16, label=lbl)

    plt.axvline(0, color='black', linestyle='--', alpha=0.8, label='Onset')
    plt.axhline(0, color='black', linestyle='-', linewidth=0.5)
    plt.title("Antagonistic Neuron Clusters (Smoothed, Baseline-Corrected)\nSignificant Windows (post-onset)")
    plt.xlabel("Time from onset (s)")
    plt.ylabel("Mean Normalized Difference (Like - Dislike)")
    plt.legend(frameon=False)
    plt.grid(True, alpha=0.15)

    out_pth_sig = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results/antagonistic_clusters_like_dislike_smoothed_sig_windows.png"
    plt.savefig(out_pth_sig, dpi=200)
    plt.close()
    print(f"Smoothed analysis complete. Plot saved to {out_pth}")
    print(f"Smoothed analysis with significant windows saved to {out_pth_sig}")

if __name__ == "__main__":
    analyze()
