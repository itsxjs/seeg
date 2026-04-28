from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.signal as sps
from scipy.stats import ttest_rel
from statsmodels.tsa.stattools import grangercausalitytests

from ah_pipeline.config import PipelineConfig
from ah_pipeline.connectivity_stats import _pick_region_pairs
from ah_pipeline.nwb_io import load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recompute theta-band arousal sGC with a lower model order and plot theta/beta together."
    )
    p.add_argument("--data-dir", type=Path, default=Path("data/000623"))
    p.add_argument(
        "--arousal-csv",
        type=Path,
        default=Path("results/arousal_short_local_3b_fix_full/arousal_segments.csv"),
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        default=Path("results/sgc_arousal_all_subjects"),
    )
    p.add_argument("--maxlag", type=int, default=3)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def _fdr_bh(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    out = np.zeros_like(p, dtype=bool)
    ok = np.isfinite(p)
    if not np.any(ok):
        return out
    idx = np.where(ok)[0]
    pv = p[idx]
    order = np.argsort(pv)
    pv_sorted = pv[order]
    ranks = np.arange(1, len(pv_sorted) + 1)
    passed = pv_sorted <= alpha * ranks / len(pv_sorted)
    if not np.any(passed):
        return out
    cutoff = pv_sorted[np.max(np.where(passed)[0])]
    out[idx] = pv <= cutoff
    return out


def _subject_from_run_id(run_id: str) -> str:
    return run_id.split("_")[0]


def _existing_success_run_ids(input_dir: Path) -> list[str]:
    run_dir = input_dir / "connectivity_arousal"
    paths = sorted(p for p in run_dir.glob("*_arousal_sgc.csv") if not p.name.startswith("._"))
    run_ids = []
    for path in paths:
        try:
            df = pd.read_csv(path, usecols=["band"])
        except Exception:
            continue
        if not df.empty:
            run_ids.append(path.name.removesuffix("_arousal_sgc.csv"))
    return run_ids


def _map_nwbs(data_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in data_dir.rglob("*.nwb"):
        if path.name.startswith("._") or "behavior+ecephys" not in path.name:
            continue
        out[path.stem.lower()] = path
    return out


def _make_events(arousal_csv: Path, subject: str) -> pd.DataFrame:
    arousal_df = pd.read_csv(arousal_csv)
    events = arousal_df[["center_sec"]].rename(columns={"center_sec": "onset"})
    events["subject"] = subject
    events["valence"] = "neutral"
    events["event_type"] = "arousal_segment"
    return events[["subject", "onset", "valence", "event_type"]]


def _compute_theta_for_run(nwb_path: Path, arousal_csv: Path, cfg: PipelineConfig, maxlag: int) -> pd.DataFrame:
    run_id = nwb_path.stem.lower()
    subject = _subject_from_run_id(run_id)
    sig = load_subject_lfp_from_nwb(nwb_path)
    sig_pp = preprocess_signal(sig, cfg)
    events = _make_events(arousal_csv, subject)
    ep = epoch_subject(sig_pp, events, cfg)
    ep_clean, _ = run_hybrid_qc(ep, cfg)

    pairs = _pick_region_pairs(ep_clean.channel_names, sig_pp.region)
    sos = sps.butter(4, [4.0, 8.0], btype="bandpass", fs=ep_clean.sfreq, output="sos")

    rows: list[dict[str, object]] = []
    for tr in range(ep_clean.data.shape[0]):
        valence = str(ep_clean.trial_info.iloc[tr]["valence"])
        for ia, ih, pair_name in pairs:
            xa = sps.sosfiltfilt(sos, ep_clean.data[tr, ia])
            yh = sps.sosfiltfilt(sos, ep_clean.data[tr, ih])
            try:
                res_ah = grangercausalitytests(np.column_stack([yh, xa]), maxlag=maxlag, verbose=False)
                res_ha = grangercausalitytests(np.column_stack([xa, yh]), maxlag=maxlag, verbose=False)
                f_ah = max(v[0]["ssr_ftest"][0] for v in res_ah.values())
                f_ha = max(v[0]["ssr_ftest"][0] for v in res_ha.values())
            except Exception:
                f_ah = np.nan
                f_ha = np.nan
            rows.append(
                {
                    "subject": subject,
                    "run_id": run_id,
                    "trial": tr,
                    "pair": pair_name,
                    "band": "theta",
                    "A_to_H_gc": f_ah,
                    "H_to_A_gc": f_ha,
                    "valence": valence,
                    "theta_maxlag": maxlag,
                }
            )
    return pd.DataFrame(rows)


def _subject_band_summary(df: pd.DataFrame, band: str) -> pd.DataFrame:
    part = df[df["band"] == band].copy()
    part["A_to_H_gc"] = pd.to_numeric(part["A_to_H_gc"], errors="coerce")
    part["H_to_A_gc"] = pd.to_numeric(part["H_to_A_gc"], errors="coerce")
    return (
        part.groupby("subject", as_index=False)[["A_to_H_gc", "H_to_A_gc"]]
        .mean(numeric_only=True)
        .dropna(subset=["A_to_H_gc", "H_to_A_gc"], how="any")
    )


def _band_stats(summary: pd.DataFrame) -> dict[str, object]:
    a = summary["A_to_H_gc"].to_numpy(dtype=float)
    h = summary["H_to_A_gc"].to_numpy(dtype=float)
    ok = np.isfinite(a) & np.isfinite(h)
    a = a[ok]
    h = h[ok]
    if len(a) >= 3:
        t_stat, p_val = ttest_rel(a, h, nan_policy="omit")
    else:
        t_stat, p_val = np.nan, np.nan
    return {
        "n_subjects": int(len(a)),
        "A_to_H_mean": None if len(a) == 0 else float(np.mean(a)),
        "H_to_A_mean": None if len(h) == 0 else float(np.mean(h)),
        "A_to_H_sem": None if len(a) == 0 else float(np.std(a, ddof=0) / np.sqrt(len(a))),
        "H_to_A_sem": None if len(h) == 0 else float(np.std(h, ddof=0) / np.sqrt(len(h))),
        "paired_t": None if not np.isfinite(t_stat) else float(t_stat),
        "paired_p": None if not np.isfinite(p_val) else float(p_val),
    }


def _plot(stats: dict[str, dict[str, object]], sig_fdr: dict[str, bool], output_png: Path) -> None:
    bands = ["theta", "beta"]
    x = np.arange(len(bands))
    width = 0.34
    a_mean = [stats[b]["A_to_H_mean"] for b in bands]
    h_mean = [stats[b]["H_to_A_mean"] for b in bands]
    a_sem = [stats[b]["A_to_H_sem"] for b in bands]
    h_sem = [stats[b]["H_to_A_sem"] for b in bands]

    fig, ax = plt.subplots(figsize=(9.2, 5.6), dpi=200)
    ax.bar(x - width / 2, a_mean, width=width, yerr=a_sem, capsize=4, color="#c44e52", alpha=0.9, label="A->H")
    ax.bar(x + width / 2, h_mean, width=width, yerr=h_sem, capsize=4, color="#4c72b0", alpha=0.9, label="H->A")

    y_max = np.nanmax(np.array(a_mean + h_mean, dtype=float) + np.array(a_sem + h_sem, dtype=float))
    if not np.isfinite(y_max):
        y_max = 1.0
    for i, band in enumerate(bands):
        p_val = stats[band]["paired_p"]
        p_txt = "p=n/a" if p_val is None else f"p={p_val:.3g}"
        star = "*" if sig_fdr.get(band, False) else ""
        ax.text(
            x[i],
            y_max * 1.06,
            f"n={stats[band]['n_subjects']}\n{p_txt}{star}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(["theta (4-8 Hz)", "beta (13-30 Hz)"])
    ax.set_ylabel("Granger causality F (subject mean)")
    ax.set_title("Arousal segments: A-H directional sGC")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper right")
    ax.set_ylim(0, y_max * 1.25)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    warnings.filterwarnings("ignore", message=".*verbose is deprecated.*")
    warnings.filterwarnings("ignore", message=".*covariance of constraints does not have full rank.*")
    args = parse_args()
    args.input_dir.mkdir(parents=True, exist_ok=True)

    theta_dir = args.input_dir / f"theta_lowlag_maxlag{args.maxlag}"
    theta_dir.mkdir(parents=True, exist_ok=True)

    run_ids = _existing_success_run_ids(args.input_dir)
    nwb_by_run = _map_nwbs(args.data_dir)
    missing = [r for r in run_ids if r not in nwb_by_run]
    if missing:
        print(f"warning: missing NWB for {len(missing)} successful run IDs")

    cfg = PipelineConfig(data_dir=args.data_dir, event_csv=None, output_dir=args.input_dir)
    theta_paths: list[Path] = []
    for idx, run_id in enumerate(run_ids, start=1):
        if run_id not in nwb_by_run:
            continue
        out_csv = theta_dir / f"{run_id}_theta_maxlag{args.maxlag}_sgc.csv"
        theta_paths.append(out_csv)
        if out_csv.exists() and not args.force:
            print(f"[{idx}/{len(run_ids)}] cached {run_id}")
            continue
        print(f"[{idx}/{len(run_ids)}] computing {run_id}", flush=True)
        theta_df = _compute_theta_for_run(nwb_by_run[run_id], args.arousal_csv, cfg, args.maxlag)
        theta_df.to_csv(out_csv, index=False)
        finite = np.isfinite(theta_df["A_to_H_gc"]) & np.isfinite(theta_df["H_to_A_gc"])
        print(f"[{idx}/{len(run_ids)}] saved {out_csv.name} finite={int(finite.sum())}/{len(theta_df)}", flush=True)

    theta_frames = [pd.read_csv(p) for p in theta_paths if p.exists()]
    if not theta_frames:
        raise RuntimeError("No theta result files were created")
    theta_all = pd.concat(theta_frames, ignore_index=True)
    theta_combined = args.input_dir / f"combined_arousal_sgc_theta_maxlag{args.maxlag}.csv"
    theta_all.to_csv(theta_combined, index=False)

    beta_all = pd.read_csv(args.input_dir / "combined_arousal_sgc.csv")
    theta_subj = _subject_band_summary(theta_all, "theta")
    beta_subj = _subject_band_summary(beta_all, "beta")

    theta_subj.to_csv(args.input_dir / f"subject_theta_sgc_maxlag{args.maxlag}.csv", index=False)
    beta_subj.to_csv(args.input_dir / "subject_beta_sgc_original.csv", index=False)

    stats = {
        "theta": _band_stats(theta_subj),
        "beta": _band_stats(beta_subj),
    }
    pvals = np.array([stats["theta"]["paired_p"], stats["beta"]["paired_p"]], dtype=float)
    sig = _fdr_bh(pvals, alpha=0.05)
    sig_fdr = {"theta": bool(sig[0]), "beta": bool(sig[1])}

    output_png = args.input_dir / f"arousal_sgc_direction_theta_beta_maxlag{args.maxlag}.png"
    _plot(stats, sig_fdr, output_png)

    summary = {
        "theta_method": {
            "band_hz": [4.0, 8.0],
            "maxlag": args.maxlag,
            "reason": "Original maxlag=10 produced all-NaN theta sGC for 2 s arousal epochs; maxlag=3 produced finite estimates in validation.",
        },
        "theta_rows": int(len(theta_all)),
        "theta_finite_both": int((np.isfinite(theta_all["A_to_H_gc"]) & np.isfinite(theta_all["H_to_A_gc"])).sum()),
        "stats": stats,
        "sig_fdr_q05": sig_fdr,
        "figure": str(output_png),
        "theta_combined_csv": str(theta_combined),
    }
    summary_path = args.input_dir / f"arousal_theta_beta_sgc_stats_maxlag{args.maxlag}.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"saved {theta_combined}")
    print(f"saved {output_png}")
    print(f"saved {summary_path}")


if __name__ == "__main__":
    main()
