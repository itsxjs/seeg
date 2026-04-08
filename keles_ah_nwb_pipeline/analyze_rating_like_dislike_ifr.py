from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import h5py
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats import wilcoxon


def fdr_bh(pvals: np.ndarray) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan, dtype=float)
    ok = np.isfinite(p)
    if not np.any(ok):
        return out

    pv = p[ok]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    q = ranked * m / (np.arange(1, m + 1))
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0.0, 1.0)

    unsorted = np.empty_like(q)
    unsorted[order] = q
    out[ok] = unsorted
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze rating like/dislike IFR (overall/amygdala/hippocampus)")
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
        if ("海马" in area) or ("hipp" in low):
            hipp.add(idx)

    return amyg, hipp


def trial_ifr_for_channel(
    spike_sec: np.ndarray,
    event_sec: np.ndarray,
    tmin: float,
    tmax: float,
    bin_edges: np.ndarray,
    smooth_sigma_bins: float,
) -> np.ndarray:
    n_trials = len(event_sec)
    n_bins = len(bin_edges) - 1
    bin_s = float(bin_edges[1] - bin_edges[0])
    out = np.zeros((n_trials, n_bins), dtype=float)

    sp = np.asarray(spike_sec, dtype=float)
    for i, e in enumerate(event_sec.astype(float)):
        rel = sp - e
        rel = rel[(rel >= tmin) & (rel < tmax)]
        if rel.size == 0:
            continue
        cnt, _ = np.histogram(rel, bins=bin_edges)
        out[i] = cnt.astype(float) / max(bin_s, 1e-12)

    if smooth_sigma_bins > 0:
        out = gaussian_filter1d(out, sigma=smooth_sigma_bins, axis=1, mode="nearest")

    return out


def mean_curve_and_delta(
    mat: np.ndarray,
    t: np.ndarray,
    baseline_win: tuple[float, float],
    response_win: tuple[float, float],
) -> tuple[np.ndarray, float]:
    curve = np.mean(mat, axis=0) if len(mat) else np.zeros(len(t), dtype=float)
    bidx = (t >= baseline_win[0]) & (t < baseline_win[1])
    ridx = (t >= response_win[0]) & (t < response_win[1])
    if not np.any(bidx) or not np.any(ridx) or len(mat) == 0:
        return curve, np.nan
    trial_base = np.mean(mat[:, bidx], axis=1)
    trial_resp = np.mean(mat[:, ridx], axis=1)
    delta = float(np.mean(trial_resp - trial_base))
    return curve, delta


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ev = pd.read_csv(args.events_csv)
    if "rating_c3" not in ev.columns:
        raise ValueError("rating_c3 not found in events csv")

    rating = ev[ev["phase"] == "rating"].copy()
    like = rating[rating["rating_c3"].isin([4, 5])].copy()
    dislike = rating[rating["rating_c3"].isin([1, 2])].copy()

    if len(like) == 0 or len(dislike) == 0:
        raise RuntimeError("No like/dislike rating trials found in rating_c3.")

    fs_vals = np.unique(ev["fs"].dropna().to_numpy(dtype=float))
    if len(fs_vals) != 1:
        raise RuntimeError(f"Expected single fs in events csv, got: {fs_vals}")
    fs = float(fs_vals[0])

    spikes = load_spike_tps_samples(args.spike_mat)
    n_ch = len(spikes)

    amyg_set, hipp_set = parse_region_channels(args.electrodes_xml)
    amyg_idx = sorted(i for i in amyg_set if 0 <= i < n_ch)
    hipp_idx = sorted(i for i in hipp_set if 0 <= i < n_ch)
    overall_idx = list(range(n_ch))

    bin_s = args.bin_ms / 1000.0
    bin_edges = np.arange(args.tmin, args.tmax + bin_s, bin_s)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    smooth_sigma_bins = (args.smooth_ms / 1000.0) / max(bin_s, 1e-12)

    like_sec = like["onset_sec"].to_numpy(dtype=float)
    dislike_sec = dislike["onset_sec"].to_numpy(dtype=float)

    like_mats: list[np.ndarray] = []
    dislike_mats: list[np.ndarray] = []
    per_ch_rows: list[dict[str, object]] = []

    for ch_i, sp in enumerate(spikes):
        sp_sec = sp.astype(float) / fs
        m_like = trial_ifr_for_channel(
            spike_sec=sp_sec,
            event_sec=like_sec,
            tmin=args.tmin,
            tmax=args.tmax,
            bin_edges=bin_edges,
            smooth_sigma_bins=smooth_sigma_bins,
        )
        m_dis = trial_ifr_for_channel(
            spike_sec=sp_sec,
            event_sec=dislike_sec,
            tmin=args.tmin,
            tmax=args.tmax,
            bin_edges=bin_edges,
            smooth_sigma_bins=smooth_sigma_bins,
        )
        like_mats.append(m_like)
        dislike_mats.append(m_dis)

        c_like, d_like = mean_curve_and_delta(m_like, bin_centers, tuple(args.baseline_win), tuple(args.response_win))
        c_dis, d_dis = mean_curve_and_delta(m_dis, bin_centers, tuple(args.baseline_win), tuple(args.response_win))

        if ch_i in amyg_set:
            region = "amygdala"
        elif ch_i in hipp_set:
            region = "hippocampus"
        else:
            region = "other"

        per_ch_rows.append(
            {
                "channel_1based": ch_i + 1,
                "channel_0based": ch_i,
                "region": region,
                "like_delta_hz": d_like,
                "dislike_delta_hz": d_dis,
                "delta_diff_like_minus_dislike_hz": d_like - d_dis if np.isfinite(d_like) and np.isfinite(d_dis) else np.nan,
                "n_like_trials": len(like_sec),
                "n_dislike_trials": len(dislike_sec),
            }
        )

    def region_curve(ch_idx: list[int]) -> tuple[np.ndarray, np.ndarray]:
        if len(ch_idx) == 0:
            return np.full(len(bin_centers), np.nan), np.full(len(bin_centers), np.nan)
        lk = [np.mean(like_mats[i], axis=0) for i in ch_idx]
        ds = [np.mean(dislike_mats[i], axis=0) for i in ch_idx]
        return np.mean(np.stack(lk, axis=0), axis=0), np.mean(np.stack(ds, axis=0), axis=0)

    ov_like, ov_dis = region_curve(overall_idx)
    am_like, am_dis = region_curve(amyg_idx)
    hp_like, hp_dis = region_curve(hipp_idx)

    curve_df = pd.DataFrame(
        {
            "time_s": bin_centers,
            "overall_like_hz": ov_like,
            "overall_dislike_hz": ov_dis,
            "amygdala_like_hz": am_like,
            "amygdala_dislike_hz": am_dis,
            "hippocampus_like_hz": hp_like,
            "hippocampus_dislike_hz": hp_dis,
        }
    )

    per_ch_df = pd.DataFrame(per_ch_rows)

    def region_time_stats(name: str, idx: list[int]) -> pd.DataFrame:
        if len(idx) == 0:
            return pd.DataFrame(
                {
                    "region": [name] * len(bin_centers),
                    "time_s": bin_centers,
                    "like_mean_hz": np.nan,
                    "like_std_hz": np.nan,
                    "dislike_mean_hz": np.nan,
                    "dislike_std_hz": np.nan,
                    "diff_mean_hz": np.nan,
                    "p_raw": np.nan,
                    "p_fdr": np.nan,
                }
            )

        like_curves = np.stack([np.mean(like_mats[i], axis=0) for i in idx], axis=0)
        dislike_curves = np.stack([np.mean(dislike_mats[i], axis=0) for i in idx], axis=0)
        diff_curves = like_curves - dislike_curves

        like_mean = np.mean(like_curves, axis=0)
        dislike_mean = np.mean(dislike_curves, axis=0)
        like_std = np.std(like_curves, axis=0, ddof=1) if like_curves.shape[0] > 1 else np.zeros_like(like_mean)
        dislike_std = np.std(dislike_curves, axis=0, ddof=1) if dislike_curves.shape[0] > 1 else np.zeros_like(dislike_mean)
        diff_mean = np.mean(diff_curves, axis=0)

        p_raw = np.full(len(bin_centers), np.nan, dtype=float)
        if diff_curves.shape[0] >= 6:
            for j in range(diff_curves.shape[1]):
                x = diff_curves[:, j]
                if not np.allclose(x, 0.0):
                    try:
                        _s, p = wilcoxon(x)
                        p_raw[j] = float(p)
                    except ValueError:
                        p_raw[j] = np.nan
                else:
                    p_raw[j] = 1.0

        p_fdr = fdr_bh(p_raw)

        return pd.DataFrame(
            {
                "region": [name] * len(bin_centers),
                "time_s": bin_centers,
                "like_mean_hz": like_mean,
                "like_std_hz": like_std,
                "dislike_mean_hz": dislike_mean,
                "dislike_std_hz": dislike_std,
                "diff_mean_hz": diff_mean,
                "p_raw": p_raw,
                "p_fdr": p_fdr,
            }
        )

    time_stats_df = pd.concat(
        [
            region_time_stats("overall", overall_idx),
            region_time_stats("amygdala", amyg_idx),
            region_time_stats("hippocampus", hipp_idx),
        ],
        axis=0,
        ignore_index=True,
    )

    def summarize_region(name: str, idx: list[int]) -> dict[str, object]:
        d = per_ch_df[per_ch_df["channel_0based"].isin(idx)]
        like_d = d["like_delta_hz"].to_numpy(dtype=float)
        dis_d = d["dislike_delta_hz"].to_numpy(dtype=float)
        diff = like_d - dis_d
        mask = np.isfinite(diff)
        like_d = like_d[mask]
        dis_d = dis_d[mask]
        diff = diff[mask]

        p = np.nan
        if len(diff) >= 6 and not np.allclose(diff, 0.0):
            try:
                _s, p = wilcoxon(diff)
                p = float(p)
            except ValueError:
                p = np.nan

        return {
            "region": name,
            "n_channels": int(len(diff)),
            "n_like_trials": int(len(like_sec)),
            "n_dislike_trials": int(len(dislike_sec)),
            "like_delta_mean_hz": float(np.mean(like_d)) if len(like_d) else np.nan,
            "dislike_delta_mean_hz": float(np.mean(dis_d)) if len(dis_d) else np.nan,
            "mean_diff_like_minus_dislike_hz": float(np.mean(diff)) if len(diff) else np.nan,
            "wilcoxon_p": p,
        }

    stats_df = pd.DataFrame(
        [
            summarize_region("overall", overall_idx),
            summarize_region("amygdala", amyg_idx),
            summarize_region("hippocampus", hipp_idx),
        ]
    )

    curve_csv = args.output_dir / "rating_c3_like45_dislike12_ifr_curves.csv"
    ch_csv = args.output_dir / "rating_c3_like45_dislike12_ifr_per_channel.csv"
    stat_csv = args.output_dir / "rating_c3_like45_dislike12_ifr_stats.csv"
    time_stat_csv = args.output_dir / "rating_c3_like45_dislike12_ifr_time_stats.csv"

    curve_df.to_csv(curve_csv, index=False)
    per_ch_df.to_csv(ch_csv, index=False)
    stats_df.to_csv(stat_csv, index=False)
    time_stats_df.to_csv(time_stat_csv, index=False)

    print("saved", curve_csv)
    print("saved", ch_csv)
    print("saved", stat_csv)
    print("saved", time_stat_csv)
    print("like_n", len(like_sec), "dislike_n", len(dislike_sec), "amyg_n", len(amyg_idx), "hipp_n", len(hipp_idx))
    print(stats_df.to_string(index=False))


if __name__ == "__main__":
    main()
