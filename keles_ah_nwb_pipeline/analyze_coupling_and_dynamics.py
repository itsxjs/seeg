"""
Analyze intra-region vs inter-region coupling strength and temporal dynamics.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from itertools import combinations

import h5py
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats import pearsonr, spearmanr


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze coupling strength and temporal dynamics")
    p.add_argument("--events-csv", type=Path, required=True)
    p.add_argument("--spike-mat", type=Path, required=True)
    p.add_argument("--electrodes-xml", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--tmin", type=float, default=-0.5)
    p.add_argument("--tmax", type=float, default=2.0)
    p.add_argument("--bin-ms", type=float, default=10.0)
    p.add_argument("--smooth-ms", type=float, default=50.0)
    p.add_argument("--baseline-win", type=float, nargs=2, default=(-0.5, 0.0))
    p.add_argument("--response-win", type=float, nargs=2, default=(0.0, 1.0))
    return p.parse_args()


def load_spike_tps_samples(spike_mat_path: Path) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    with h5py.File(spike_mat_path, "r") as f:
        refs = f["spike_Tps"][0, :]
        for r in refs:
            arr = np.asarray(f[r], dtype=np.uint32).reshape(-1)
            out.append(arr)
    return out


def parse_region_channels(electrodes_xml: Path) -> tuple[set[int], set[int]]:
    root = ET.parse(electrodes_xml).getroot()
    amyg: set[int] = set()
    hipp: set[int] = set()
    for elem in root.iter():
        if elem.tag not in ("MicroElectrodeSite", "MacroElectrodeSite"):
            continue
        area = str(elem.attrib.get("implantArea", ""))
        idx_raw = elem.attrib.get("absoluteChannelIndex", "")
        try:
            idx = int(idx_raw)
        except Exception:
            continue
        if idx < 0:
            continue
        low = area.lower()
        if ("杏仁" in area) or ("amyg" in low):
            amyg.add(idx)
        elif ("海马" in area) or ("hipp" in low):
            hipp.add(idx)
    # Fallback if XML labels absent
    if not amyg:
        amyg = set(range(16, 48))  # Assumed amygdala channels
    if not hipp:
        hipp = set(range(0, 16)) | set(range(48, 64))  # Assumed hippocampus channels
    return frozenset(amyg), frozenset(hipp)


def trial_ifr_for_channel(spike_tps_samples: list[np.ndarray], ch: int, fs: float,
                          event_t: float, tmin: float, tmax: float,
                          bin_ms: float, smooth_ms: float) -> np.ndarray:
    """Compute trial-averaged IFR for a single channel."""
    bin_s = bin_ms / 1000.0
    smooth_s = smooth_ms / 1000.0
    t_edges = np.arange(tmin, tmax + 0.5 * bin_s, bin_s)
    bins = np.digitize(spike_tps_samples[ch] / fs - event_t, t_edges) - 1
    valid = (bins >= 0) & (bins < len(t_edges) - 1)
    counts, _ = np.histogram(spike_tps_samples[ch][valid] / fs - event_t, bins=t_edges)
    ifr = counts / bin_s
    ifr = gaussian_filter1d(ifr, sigma=smooth_s / bin_s)
    return ifr


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fs = 20000.0

    events = pd.read_csv(args.events_csv)
    spike_tps_list = load_spike_tps_samples(args.spike_mat)
    amyg, hipp = parse_region_channels(args.electrodes_xml)
    
    n_ch = len(spike_tps_list)
    bin_s = args.bin_ms / 1000.0
    smooth_s = args.smooth_ms / 1000.0
    t_edges = np.arange(args.tmin, args.tmax + 0.5 * bin_s, bin_s)
    t_centers = 0.5 * (t_edges[:-1] + t_edges[1:])

    # Separate like/dislike trials
    like_mask = events["rating_c3"].isin([4, 5])
    dislike_mask = events["rating_c3"].isin([1, 2])

    # Compute per-channel, per-trial IFR
    like_trials_ifr = []  # list of (n_trials, n_channels, n_bins)
    dislike_trials_ifr = []

    for phase_name, mask in [("like", like_mask), ("dislike", dislike_mask)]:
        phase_events = events[mask]
        phase_ifr = []
        for _, row in phase_events.iterrows():
            event_t = row["onset_sec"]
            trial_ifr = []  # (n_channels, n_bins)
            for ch in range(n_ch):
                ifr = trial_ifr_for_channel(spike_tps_list, ch, fs, event_t,
                                            args.tmin, args.tmax, args.bin_ms, args.smooth_ms)
                trial_ifr.append(ifr)
            phase_ifr.append(np.array(trial_ifr))
        phase_ifr = np.array(phase_ifr)  # (n_trials, n_channels, n_bins)
        if phase_name == "like":
            like_trials_ifr = phase_ifr
        else:
            dislike_trials_ifr = phase_ifr

    print(f"like trials shape: {like_trials_ifr.shape}, dislike: {dislike_trials_ifr.shape}")

    # ===== Compute intra-region and inter-region coupling =====
    # Coupling = Pearson correlation between channel pairs within response window
    resp_start = np.searchsorted(t_centers, args.response_win[0])
    resp_end = np.searchsorted(t_centers, args.response_win[1])

    coupling_results = []

    def compute_coupling(phase_trials_ifr: np.ndarray, phase_name: str) -> None:
        """Compute coupling for a single phase (like/dislike)."""
        n_trials, n_ch, n_bins = phase_trials_ifr.shape
        
        # Intra-region coupling: average correlation within each region
        for region_name, region_ch in [("amygdala", list(amyg)), ("hippocampus", list(hipp))]:
            region_ch = [ch for ch in region_ch if ch < n_ch]
            if len(region_ch) < 2:
                continue
            
            corrs = []
            for ch1, ch2 in combinations(region_ch, 2):
                # Extract response window across all trials
                ts1 = phase_trials_ifr[:, ch1, resp_start:resp_end].flatten()
                ts2 = phase_trials_ifr[:, ch2, resp_start:resp_end].flatten()
                if len(ts1) > 2:
                    valid = np.isfinite(ts1) & np.isfinite(ts2)
                    if np.sum(valid) > 2:
                        r, p = pearsonr(ts1[valid], ts2[valid])
                        if np.isfinite(r):
                            corrs.append(r)
            
            if corrs:
                mean_corr = np.mean(corrs)
                std_corr = np.std(corrs)
                coupling_results.append({
                    "coupling_type": "intra_region",
                    "region": region_name,
                    "phase": phase_name,
                    "mean_corr": mean_corr,
                    "std_corr": std_corr,
                    "n_pairs": len(corrs),
                })

        # Inter-region coupling: correlation between amygdala and hippocampus
        amyg_ch = [ch for ch in amyg if ch < n_ch]
        hipp_ch = [ch for ch in hipp if ch < n_ch]
        if len(amyg_ch) > 0 and len(hipp_ch) > 0:
            corrs = []
            for ch1 in amyg_ch:
                for ch2 in hipp_ch:
                    ts1 = phase_trials_ifr[:, ch1, resp_start:resp_end].flatten()
                    ts2 = phase_trials_ifr[:, ch2, resp_start:resp_end].flatten()
                    if len(ts1) > 2:
                        valid = np.isfinite(ts1) & np.isfinite(ts2)
                        if np.sum(valid) > 2:
                            r, p = pearsonr(ts1[valid], ts2[valid])
                            if np.isfinite(r):
                                corrs.append(r)
            
            if corrs:
                mean_corr = np.mean(corrs)
                std_corr = np.std(corrs)
                coupling_results.append({
                    "coupling_type": "inter_region",
                    "region": "amygdala-hippocampus",
                    "phase": phase_name,
                    "mean_corr": mean_corr,
                    "std_corr": std_corr,
                    "n_pairs": len(corrs),
                })

    compute_coupling(like_trials_ifr, "like")
    compute_coupling(dislike_trials_ifr, "dislike")

    coupling_df = pd.DataFrame(coupling_results)
    coupling_out = args.output_dir / "coupling_strength.csv"
    coupling_df.to_csv(coupling_out, index=False)
    print(f"saved {coupling_out}")

    # ===== Compute temporal dynamics (slopes and derivatives) =====
    dynamics_results = []

    def compute_dynamics(phase_trials_ifr: np.ndarray, phase_name: str) -> None:
        """Compute temporal dynamics: slope and acceleration."""
        n_trials, n_ch, n_bins = phase_trials_ifr.shape
        
        # Per-channel: compute slope (dIFR/dt) and acceleration
        for ch in range(n_ch):
            ch_ifr = phase_trials_ifr[:, ch, :]  # (n_trials, n_bins)
            mean_ifr = np.mean(ch_ifr, axis=0)  # (n_bins,)
            
            # Slope in response window
            resp_ifr = mean_ifr[resp_start:resp_end]
            if len(resp_ifr) > 2:
                t_resp = t_centers[resp_start:resp_end]
                slope = np.polyfit(t_resp, resp_ifr, 1)[0]  # dHz/s
            else:
                slope = np.nan
            
            # Peak response timing
            peak_idx = np.argmax(np.abs(resp_ifr))
            peak_time = t_centers[resp_start + peak_idx]
            peak_ifr = resp_ifr[peak_idx]
            
            # Early vs late response (first half vs second half of response window)
            mid_idx = len(resp_ifr) // 2
            early_mean = np.mean(resp_ifr[:mid_idx]) if mid_idx > 0 else resp_ifr[0]
            late_mean = np.mean(resp_ifr[mid_idx:])
            
            region_name = "amygdala" if ch in amyg else ("hippocampus" if ch in hipp else "other")
            
            dynamics_results.append({
                "channel": ch,
                "region": region_name,
                "phase": phase_name,
                "response_slope_hz_per_s": slope,
                "peak_time_s": peak_time,
                "peak_ifr_hz": peak_ifr,
                "early_mean_hz": early_mean,
                "late_mean_hz": late_mean,
                "early_late_diff_hz": late_mean - early_mean,
            })

    compute_dynamics(like_trials_ifr, "like")
    compute_dynamics(dislike_trials_ifr, "dislike")

    dynamics_df = pd.DataFrame(dynamics_results)
    dynamics_out = args.output_dir / "temporal_dynamics.csv"
    dynamics_df.to_csv(dynamics_out, index=False)
    print(f"saved {dynamics_out}")

    # ===== Summary statistics =====
    print("\n=== Coupling Strength Summary ===")
    print(coupling_df.groupby(["coupling_type", "phase"])[["mean_corr"]].mean())
    
    print("\n=== Temporal Dynamics Summary ===")
    dyn_summary = dynamics_df.groupby(["region", "phase"])[["response_slope_hz_per_s", "early_late_diff_hz"]].mean()
    print(dyn_summary)


if __name__ == "__main__":
    main()
