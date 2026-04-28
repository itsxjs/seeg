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


def trimmed_mean_sem(curves, trim_frac=0.2):
    """Compute mean/SEM after trimming extremes to reduce outlier-driven uncertainty."""
    curves = np.asarray(curves)
    n = curves.shape[0]
    if n == 0:
        z = np.zeros(curves.shape[1])
        return z, z

    k = int(np.floor(n * trim_frac))
    sorted_curves = np.sort(curves, axis=0)
    if 2 * k < n:
        trimmed = sorted_curves[k:n - k]
    else:
        trimmed = sorted_curves

    mean_curve = np.mean(trimmed, axis=0)
    n_eff = trimmed.shape[0]
    if n_eff > 1:
        sem_curve = np.std(trimmed, axis=0, ddof=1) / np.sqrt(n_eff)
    else:
        sem_curve = np.zeros(trimmed.shape[1])
    return mean_curve, sem_curve


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
    ifr_raw_like = []
    ifr_raw_dislike = []
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
                return gaussian_filter1d(curve, sigma=SMOOTH_SIGMA)

            cur_like = baseline_correct(get_ifr(like_onsets))
            cur_dislike = baseline_correct(get_ifr(dislike_onsets))
            
            # Feature for clustering: Normalized difference (to group by PATTERN)
            diff = cur_like - cur_dislike
            if np.max(np.abs(diff)) > 0.01: 
                diff_norm = diff / (np.max(np.abs(diff)) + 1e-6)
                spike_features.append(diff_norm)
                ifr_raw_like.append(cur_like)
                ifr_raw_dislike.append(cur_dislike)
                unit_ids.append(f"{sub_id}_u{i}")
                
    if not spike_features:
        return np.empty((0, len(BINS)-1)), np.empty((0, len(BINS)-1)), np.empty((0, len(BINS)-1)), []
    return np.array(spike_features), np.array(ifr_raw_like), np.array(ifr_raw_dislike), unit_ids

def analyze():
    all_features = []
    all_raw_like = []
    all_raw_dislike = []
    all_meta = []
    
    for sub, config in SUBJECTS.items():
        feat, raw_l, raw_d, ids = load_data(sub, config)
        if feat.size > 0:
            all_features.append(feat)
            all_raw_like.append(raw_l)
            all_raw_dislike.append(raw_d)
            all_meta.extend(ids)
    
    X = np.vstack(all_features)
    Y_like = np.vstack(all_raw_like)
    Y_dislike = np.vstack(all_raw_dislike)
    
    # Clustering by pattern (normalized diff)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X)
    
    # Plotting RAW IFR (line-only, original figure)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    cluster_names = ["Cluster 0", "Cluster 1"]
    
    for c in [0, 1]:
        idx = (clusters == c)
        n_units = np.sum(idx)
        
        # Calculate cluster-level raw IFR means
        like_mean = np.mean(Y_like[idx], axis=0)
        like_sem = np.std(Y_like[idx], axis=0) / np.sqrt(n_units)
        
        dislike_mean = np.mean(Y_dislike[idx], axis=0)
        dislike_sem = np.std(Y_dislike[idx], axis=0) / np.sqrt(n_units)
        
        ax = axes[c]
        ax.plot(BIN_CENTERS, like_mean, color='red', label='Like (4,5)')
        
        ax.plot(BIN_CENTERS, dislike_mean, color='blue', label='Dislike (1,2)')
        
        ax.axvline(0, color='black', linestyle='--')
        ax.set_title(f"{cluster_names[c]} (n={n_units} units)")
        ax.set_xlabel("Time from onset (s)")
        ax.legend(frameon=False)
        ax.grid(True, alpha=0.15)

    axes[0].set_ylabel("Raw Firing Rate (Hz)")
    plt.suptitle("Raw IFR Responses by Antagonistic Clusters\nCross-Subject Analysis")
    plt.tight_layout()
    
    out_pth = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results/antagonistic_clusters_raw_ifr.png"
    plt.savefig(out_pth, dpi=200)
    plt.close(fig)

    # Plotting RAW IFR with SEM shading (new figure, no overwrite)
    fig_shade, axes_shade = plt.subplots(1, 2, figsize=(15, 6), sharey=True)

    for c in [0, 1]:
        idx = (clusters == c)
        n_units = np.sum(idx)

        like_mean = np.mean(Y_like[idx], axis=0)
        like_sem = np.std(Y_like[idx], axis=0) / np.sqrt(n_units)

        dislike_mean = np.mean(Y_dislike[idx], axis=0)
        dislike_sem = np.std(Y_dislike[idx], axis=0) / np.sqrt(n_units)

        ax = axes_shade[c]
        ax.plot(BIN_CENTERS, like_mean, color='red', label='Like (4,5)')
        ax.fill_between(
            BIN_CENTERS,
            like_mean - like_sem,
            like_mean + like_sem,
            color='red',
            alpha=0.2,
            linewidth=0,
        )

        ax.plot(BIN_CENTERS, dislike_mean, color='blue', label='Dislike (1,2)')
        ax.fill_between(
            BIN_CENTERS,
            dislike_mean - dislike_sem,
            dislike_mean + dislike_sem,
            color='blue',
            alpha=0.2,
            linewidth=0,
        )

        ax.axvline(0, color='black', linestyle='--')
        ax.set_title(f"{cluster_names[c]} (n={n_units} units)")
        ax.set_xlabel("Time from onset (s)")
        ax.legend(frameon=False)
        ax.grid(True, alpha=0.15)

    axes_shade[0].set_ylabel("Raw Firing Rate (Hz)")
    plt.suptitle("Raw IFR Responses by Antagonistic Clusters (Mean ± SEM)\nCross-Subject Analysis")
    plt.tight_layout()

    out_pth_shade = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results/antagonistic_clusters_raw_ifr_with_sem.png"
    plt.savefig(out_pth_shade, dpi=200)
    plt.close(fig_shade)

    # Plotting RAW IFR with robust SEM shading + significant windows (new figure)
    fig_sig, axes_sig = plt.subplots(1, 2, figsize=(15, 6), sharey=True)

    for c in [0, 1]:
        idx = (clusters == c)
        n_units = np.sum(idx)

        like_curves = Y_like[idx]
        dislike_curves = Y_dislike[idx]
        like_mean, like_sem = trimmed_mean_sem(like_curves, trim_frac=0.2)
        dislike_mean, dislike_sem = trimmed_mean_sem(dislike_curves, trim_frac=0.2)

        _, pvals = stats.ttest_rel(like_curves, dislike_curves, axis=0, nan_policy='omit')
        sig_mask = fdr_bh(pvals, alpha=0.05)
        sig_mask = sig_mask & (BIN_CENTERS >= SIG_START)
        sig_windows = contiguous_sig_windows(sig_mask, BIN_CENTERS, BIN_SIZE, min_bins=2)

        ax = axes_sig[c]
        ax.plot(BIN_CENTERS, like_mean, color='red', label='Like (4,5)')
        ax.fill_between(
            BIN_CENTERS,
            like_mean - like_sem,
            like_mean + like_sem,
            color='red',
            alpha=0.12,
            linewidth=0,
        )

        ax.plot(BIN_CENTERS, dislike_mean, color='blue', label='Dislike (1,2)')
        ax.fill_between(
            BIN_CENTERS,
            dislike_mean - dislike_sem,
            dislike_mean + dislike_sem,
            color='blue',
            alpha=0.12,
            linewidth=0,
        )

        for i, (t0, t1) in enumerate(sig_windows):
            lbl = 'FDR<0.05 (>=2 bins)' if i == 0 else None
            ax.axvspan(t0, t1, color='gold', alpha=0.16, label=lbl)

        ax.axvline(0, color='black', linestyle='--')
        ax.set_title(f"{cluster_names[c]} (n={n_units} units)")
        ax.set_xlabel("Time from onset (s)")
        ax.legend(frameon=False)
        ax.grid(True, alpha=0.15)

    axes_sig[0].set_ylabel("Raw Firing Rate (Hz)")
    plt.suptitle("Baseline-Corrected IFR by Antagonistic Clusters (Robust Mean ± SEM)\nSignificant Like vs Dislike Windows (post-onset)")
    plt.tight_layout()

    out_pth_sig = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results/antagonistic_clusters_raw_ifr_with_robust_sem_sig.png"
    plt.savefig(out_pth_sig, dpi=200)
    plt.close(fig_sig)
    print(f"Raw IFR analysis complete. Plot saved to {out_pth}")
    print(f"Raw IFR (with SEM shading) plot saved to {out_pth_shade}")
    print(f"Raw IFR (robust SEM + significant windows) plot saved to {out_pth_sig}")
    print(f"Cluster 0 contains {np.sum(clusters == 0)} units.")
    print(f"Cluster 1 contains {np.sum(clusters == 1)} units.")

if __name__ == "__main__":
    analyze()
