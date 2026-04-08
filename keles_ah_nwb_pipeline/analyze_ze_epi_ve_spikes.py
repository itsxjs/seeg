from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.io as sio
from scipy.stats import wilcoxon


def _rising_edges_from_aux(aux: np.ndarray, baseline_value: int = 65532) -> np.ndarray:
    is_trig = aux != baseline_value
    return np.where(is_trig & np.r_[False, ~is_trig[:-1]])[0]


def _group_trigger_starts(starts: np.ndarray, fs: float, min_gap_sec: float) -> np.ndarray:
    if len(starts) == 0:
        return starts
    keep = np.r_[True, (np.diff(starts) / fs) >= min_gap_sec]
    return starts[keep]


def _find_gap_for_target_count(starts: np.ndarray, fs: float, target_count: int) -> tuple[float, int]:
    best_gap = 0.32
    best_n = -1
    best_err = 10**9
    for g in np.linspace(0.20, 0.80, 601):
        n = len(_group_trigger_starts(starts, fs, float(g)))
        err = abs(n - target_count)
        if err < best_err:
            best_err = err
            best_n = n
            best_gap = float(g)
        if err == 0:
            return float(g), n
    return best_gap, best_n


def _load_spike_timestamps_samples(spike_mat_path: Path) -> list[np.ndarray]:
    ch_spikes: list[np.ndarray] = []
    with h5py.File(spike_mat_path, "r") as f:
        refs = f["spike_Tps"][0, :]
        for r in refs:
            ds = f[r]
            arr = np.asarray(ds, dtype=np.uint32).reshape(-1)
            ch_spikes.append(arr)
    return ch_spikes


def _rate_windows_for_events(
    spike_samples: np.ndarray,
    event_samples: np.ndarray,
    fs: float,
    baseline_win: tuple[float, float],
    response_win: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    b0, b1 = baseline_win
    r0, r1 = response_win
    bdur = b1 - b0
    rdur = r1 - r0
    base = np.zeros(len(event_samples), dtype=float)
    resp = np.zeros(len(event_samples), dtype=float)

    sp = np.asarray(spike_samples, dtype=np.int64)
    for i, e in enumerate(event_samples.astype(np.int64)):
        bs = int(round(e + b0 * fs))
        be = int(round(e + b1 * fs))
        rs = int(round(e + r0 * fs))
        re = int(round(e + r1 * fs))
        nb = np.count_nonzero((sp >= bs) & (sp < be))
        nr = np.count_nonzero((sp >= rs) & (sp < re))
        base[i] = nb / max(bdur, 1e-12)
        resp[i] = nr / max(rdur, 1e-12)
    return base, resp


def _classify_delta(delta: np.ndarray, alpha: float = 0.05, effect_hz: float = 0.5) -> tuple[str, float, float]:
    med = float(np.median(delta)) if len(delta) else np.nan
    if len(delta) < 6:
        return "uncertain", med, np.nan
    if np.allclose(delta, 0.0):
        p = 1.0
    else:
        try:
            _s, p = wilcoxon(delta)
            p = float(p)
        except ValueError:
            p = 1.0
    if p < alpha and med >= effect_hz:
        return "up", med, p
    if p < alpha and med <= -effect_hz:
        return "down", med, p
    return "neutral", med, p


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract trigger events from aux and run spike analysis")
    p.add_argument("--raw-mat", type=Path, required=True)
    p.add_argument("--spike-mat", type=Path, required=True)
    p.add_argument("--rating-mat", type=Path, required=True)
    p.add_argument("--free-mat", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--baseline-value", type=int, default=65532)
    p.add_argument("--min-gap-sec", type=float, default=0.32)
    p.add_argument("--auto-gap-by-behavior", action="store_true")
    p.add_argument("--baseline-win", type=float, nargs=2, default=(-0.5, 0.0))
    p.add_argument("--response-win", type=float, nargs=2, default=(0.0, 1.0))
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--effect-hz", type=float, default=0.5)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rating = sio.loadmat(args.rating_mat)["ratingmatrix"]
    free = sio.loadmat(args.free_mat)["freematrix"]
    n_rating = int(rating.shape[0])
    n_free = int(free.shape[0])
    target_n = n_rating + n_free

    with h5py.File(args.raw_mat, "r") as f:
        fs = float(f["fs"][0, 0])
        aux = np.asarray(f["aux"][0, :], dtype=np.uint16)

    starts = _rising_edges_from_aux(aux, baseline_value=args.baseline_value)

    chosen_gap = float(args.min_gap_sec)
    if args.auto_gap_by_behavior:
        chosen_gap, n_found = _find_gap_for_target_count(starts, fs, target_n)
        print("auto gap", chosen_gap, "found", n_found, "target", target_n)

    events = _group_trigger_starts(starts, fs, min_gap_sec=chosen_gap)

    if len(events) != target_n:
        raise RuntimeError(
            f"Grouped trigger count {len(events)} != behavior rows {target_n}. "
            f"Try --auto-gap-by-behavior or adjust --min-gap-sec."
        )

    phase = np.array(["rating"] * n_rating + ["free"] * n_free, dtype=object)
    trial_in_phase = np.r_[np.arange(1, n_rating + 1), np.arange(1, n_free + 1)]

    evt = pd.DataFrame(
        {
            "event_id": np.arange(1, len(events) + 1),
            "phase": phase,
            "trial_in_phase": trial_in_phase,
            "onset_sample": events.astype(np.int64),
            "onset_sec": events / fs,
            "trigger_value": aux[events].astype(np.int64),
            "fs": fs,
            "group_gap_sec": chosen_gap,
        }
    )

    for c in range(rating.shape[1]):
        evt[f"rating_c{c+1}"] = np.nan
    for c in range(free.shape[1]):
        evt[f"free_c{c+1}"] = np.nan

    evt.loc[evt["phase"] == "rating", [f"rating_c{i+1}" for i in range(rating.shape[1])]] = rating
    evt.loc[evt["phase"] == "free", [f"free_c{i+1}" for i in range(free.shape[1])]] = free

    event_csv = args.output_dir / "events_from_aux_rating_free.csv"
    evt.to_csv(event_csv, index=False)

    ch_spikes = _load_spike_timestamps_samples(args.spike_mat)

    rows: list[dict[str, object]] = []
    ev_samples = evt["onset_sample"].to_numpy(dtype=np.int64)

    for ch_idx, sp in enumerate(ch_spikes, start=1):
        for ph in ["rating", "free", "all"]:
            if ph == "all":
                idx = np.arange(len(evt))
            else:
                idx = np.where(evt["phase"].to_numpy() == ph)[0]
            if len(idx) == 0:
                continue
            base, resp = _rate_windows_for_events(
                spike_samples=sp,
                event_samples=ev_samples[idx],
                fs=fs,
                baseline_win=(float(args.baseline_win[0]), float(args.baseline_win[1])),
                response_win=(float(args.response_win[0]), float(args.response_win[1])),
            )
            delta = resp - base
            cls, med, p = _classify_delta(delta, alpha=float(args.alpha), effect_hz=float(args.effect_hz))
            rows.append(
                {
                    "channel": ch_idx,
                    "phase": ph,
                    "n_events": int(len(idx)),
                    "n_spikes_total": int(len(sp)),
                    "baseline_rate_mean_hz": float(np.mean(base)),
                    "response_rate_mean_hz": float(np.mean(resp)),
                    "delta_rate_mean_hz": float(np.mean(delta)),
                    "delta_rate_median_hz": float(med),
                    "wilcoxon_p": float(p) if np.isfinite(p) else np.nan,
                    "class": cls,
                }
            )

    res = pd.DataFrame(rows)
    channel_csv = args.output_dir / "channel_eventlocked_summary.csv"
    res.to_csv(channel_csv, index=False)

    agg = (
        res.groupby("phase")
        .agg(
            n_channels=("channel", "nunique"),
            n_up=("class", lambda s: int((s == "up").sum())),
            n_down=("class", lambda s: int((s == "down").sum())),
            n_neutral=("class", lambda s: int((s == "neutral").sum())),
            median_delta_hz=("delta_rate_median_hz", "median"),
            mean_delta_hz=("delta_rate_mean_hz", "mean"),
        )
        .reset_index()
    )
    agg_csv = args.output_dir / "channel_eventlocked_phase_aggregate.csv"
    agg.to_csv(agg_csv, index=False)

    print("saved", event_csv)
    print("saved", channel_csv)
    print("saved", agg_csv)
    print("n_events", len(evt), "rating", n_rating, "free", n_free, "gap_sec", chosen_gap)


if __name__ == "__main__":
    main()
