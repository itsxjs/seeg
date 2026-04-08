from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.stats import spearmanr

from ah_pipeline.config import HIPP_KEYWORDS, AMY_KEYWORDS, PipelineConfig
from ah_pipeline.nwb_io import iter_nwb_files, load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from ah_pipeline.spikes import compute_ifr_and_psth
from ah_pipeline.time_frequency import high_gamma_envelope


def _region_from_text(text: str) -> str:
    low = (text or "").lower()
    if any(k in low for k in AMY_KEYWORDS):
        return "amygdala"
    if any(k in low for k in HIPP_KEYWORDS):
        return "hippocampus"
    return "other"


def _unit_region_from_electrodes(elec_df: pd.DataFrame) -> str:
    if elec_df is None or len(elec_df) == 0:
        return "other"
    locs = elec_df.get("location", pd.Series([""] * len(elec_df))).astype(str).tolist()
    tags = {_region_from_text(v) for v in locs}
    has_a = "amygdala" in tags
    has_h = "hippocampus" in tags
    if has_a and not has_h:
        return "amygdala"
    if has_h and not has_a:
        return "hippocampus"
    if has_a and has_h:
        return "both"
    return "other"


def load_units_by_region(nwb_path: Path) -> dict[str, pd.DataFrame]:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            empty = pd.DataFrame({"spike_times": []})
            return {"amygdala": empty.copy(), "hippocampus": empty.copy(), "all": empty.copy()}

        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            empty = pd.DataFrame({"spike_times": []})
            return {"amygdala": empty.copy(), "hippocampus": empty.copy(), "all": empty.copy()}

        reg = []
        if "electrodes" in units.columns:
            for _, row in units.iterrows():
                elec = row["electrodes"]
                reg.append(_unit_region_from_electrodes(elec if isinstance(elec, pd.DataFrame) else pd.DataFrame()))
        else:
            reg = ["other"] * len(units)

        units = units[["spike_times"]].copy()
        units["region"] = reg

        units_a = units[units["region"] == "amygdala"][ ["spike_times"] ].reset_index(drop=True)
        units_h = units[units["region"] == "hippocampus"][ ["spike_times"] ].reset_index(drop=True)
        units_all = units[["spike_times"]].reset_index(drop=True)

        return {"amygdala": units_a, "hippocampus": units_h, "all": units_all}


def _resample_hg_to_ifr(hg_trials: np.ndarray, t_src: np.ndarray, ifr_time: np.ndarray) -> np.ndarray:
    out = np.zeros((hg_trials.shape[0], len(ifr_time)), dtype=np.float32)
    for i in range(hg_trials.shape[0]):
        out[i] = np.interp(ifr_time, t_src, hg_trials[i])
    return out


def _trialwise_spearman(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = min(x.shape[0], y.shape[0])
    rho = np.full(n, np.nan, dtype=float)
    pval = np.full(n, np.nan, dtype=float)
    for i in range(n):
        if np.all(np.isnan(x[i])) or np.all(np.isnan(y[i])):
            continue
        r, p = spearmanr(x[i], y[i], nan_policy="omit")
        if np.isfinite(r):
            rho[i] = float(r)
        if np.isfinite(p):
            pval[i] = float(p)
    return rho, pval


def _zscore_1d(a: np.ndarray) -> np.ndarray:
    m = np.nanmean(a)
    s = np.nanstd(a)
    if not np.isfinite(s) or s < 1e-12:
        return np.zeros_like(a)
    return (a - m) / s


def _trialwise_ifr_lag(ifr_a: np.ndarray, ifr_h: np.ndarray, bin_ms: float, max_lag_ms: float = 300.0) -> tuple[np.ndarray, np.ndarray]:
    n = min(ifr_a.shape[0], ifr_h.shape[0])
    lag_samp = int(round(max_lag_ms / bin_ms))
    lags_ms = np.full(n, np.nan, dtype=float)
    peak_corr = np.full(n, np.nan, dtype=float)

    for i in range(n):
        xa = _zscore_1d(np.asarray(ifr_a[i], dtype=float))
        xh = _zscore_1d(np.asarray(ifr_h[i], dtype=float))
        if xa.size == 0 or xh.size == 0:
            continue
        c = np.correlate(xa, xh, mode="full") / max(len(xa), 1)
        lags = np.arange(-len(xa) + 1, len(xh))
        keep = np.where((lags >= -lag_samp) & (lags <= lag_samp))[0]
        if keep.size == 0:
            continue
        ck = c[keep]
        lk = lags[keep]
        j = int(np.nanargmax(ck))
        # lag > 0: ifr_h needs to be shifted later to align with ifr_a, interpreted as A leads H.
        lags_ms[i] = float(lk[j] * bin_ms)
        peak_corr[i] = float(ck[j])

    return lags_ms, peak_corr


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Region-aware spike batch analysis (A/H IFR + coupling)")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--event-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cfg = PipelineConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        event_csv=args.event_csv,
    )

    events = load_events(args.event_csv)
    nwb_files = iter_nwb_files(args.data_dir)
    if args.max_files > 0:
        nwb_files = nwb_files[: args.max_files]

    rows: list[dict[str, object]] = []

    for nwb_path in nwb_files:
        try:
            sig = load_subject_lfp_from_nwb(nwb_path)
            sig_pp = preprocess_signal(sig, cfg)
            ep = epoch_subject(sig_pp, events, cfg)
            ep_clean, qc = run_hybrid_qc(ep, cfg)

            units_map = load_units_by_region(nwb_path)
            ua = units_map["amygdala"]
            uh = units_map["hippocampus"]
            uall = units_map["all"]

            ifr_a, ifr_t, psth_a = compute_ifr_and_psth(ua, ep_clean, cfg)
            ifr_h, _, psth_h = compute_ifr_and_psth(uh, ep_clean, cfg)
            ifr_all, _, _ = compute_ifr_and_psth(uall, ep_clean, cfg)

            hg = high_gamma_envelope(ep_clean, cfg)  # (trial, ch, time)
            region_arr = np.array(sig_pp.region)
            idx_a = np.where(region_arr == "amygdala")[0]
            idx_h = np.where(region_arr == "hippocampus")[0]

            if idx_a.size > 0:
                hg_a = np.mean(hg[:, idx_a, :], axis=1)
                hg_a_rs = _resample_hg_to_ifr(hg_a, ep_clean.times, ifr_t)
            else:
                hg_a_rs = np.full((len(ep_clean.trial_info), len(ifr_t)), np.nan, dtype=np.float32)

            if idx_h.size > 0:
                hg_h = np.mean(hg[:, idx_h, :], axis=1)
                hg_h_rs = _resample_hg_to_ifr(hg_h, ep_clean.times, ifr_t)
            else:
                hg_h_rs = np.full((len(ep_clean.trial_info), len(ifr_t)), np.nan, dtype=np.float32)

            rho_aa, p_aa = _trialwise_spearman(ifr_a, hg_a_rs)
            rho_hh, p_hh = _trialwise_spearman(ifr_h, hg_h_rs)
            rho_ah, p_ah = _trialwise_spearman(ifr_a, hg_h_rs)
            rho_ha, p_ha = _trialwise_spearman(ifr_h, hg_a_rs)

            lag_ms, lag_peak_corr = _trialwise_ifr_lag(ifr_a, ifr_h, cfg.ifr_bin_ms)

            subject_slug = sig.subject.replace("/", "_")
            np.savez_compressed(
                args.output_dir / f"{subject_slug}_region_ifr_hg.npz",
                ifr_times=ifr_t,
                ifr_all=ifr_all,
                ifr_a=ifr_a,
                ifr_h=ifr_h,
                hg_a=hg_a_rs,
                hg_h=hg_h_rs,
                psth_a_negative=psth_a.get("negative", np.array([], dtype=float)),
                psth_a_neutral=psth_a.get("neutral", np.array([], dtype=float)),
                psth_a_positive=psth_a.get("positive", np.array([], dtype=float)),
                psth_h_negative=psth_h.get("negative", np.array([], dtype=float)),
                psth_h_neutral=psth_h.get("neutral", np.array([], dtype=float)),
                psth_h_positive=psth_h.get("positive", np.array([], dtype=float)),
                rho_aa=rho_aa,
                p_aa=p_aa,
                rho_hh=rho_hh,
                p_hh=p_hh,
                rho_ah=rho_ah,
                p_ah=p_ah,
                rho_ha=rho_ha,
                p_ha=p_ha,
                lag_ms=lag_ms,
                lag_peak_corr=lag_peak_corr,
            )

            rows.append(
                {
                    "subject": sig.subject,
                    "nwb_file": str(nwb_path),
                    "n_trials": int(len(ep.trial_info)),
                    "n_clean_trials": int(len(ep_clean.trial_info)),
                    "n_units_total": int(len(uall)),
                    "n_units_a": int(len(ua)),
                    "n_units_h": int(len(uh)),
                    "n_ch_a": int(idx_a.size),
                    "n_ch_h": int(idx_h.size),
                    "rho_aa_median": float(np.nanmedian(rho_aa)) if np.any(np.isfinite(rho_aa)) else np.nan,
                    "rho_hh_median": float(np.nanmedian(rho_hh)) if np.any(np.isfinite(rho_hh)) else np.nan,
                    "rho_ah_median": float(np.nanmedian(rho_ah)) if np.any(np.isfinite(rho_ah)) else np.nan,
                    "rho_ha_median": float(np.nanmedian(rho_ha)) if np.any(np.isfinite(rho_ha)) else np.nan,
                    "sig_aa_ratio": float(np.nanmean(p_aa < 0.05)) if len(p_aa) else np.nan,
                    "sig_hh_ratio": float(np.nanmean(p_hh < 0.05)) if len(p_hh) else np.nan,
                    "sig_ah_ratio": float(np.nanmean(p_ah < 0.05)) if len(p_ah) else np.nan,
                    "sig_ha_ratio": float(np.nanmean(p_ha < 0.05)) if len(p_ha) else np.nan,
                    "lag_ms_median": float(np.nanmedian(lag_ms)) if np.any(np.isfinite(lag_ms)) else np.nan,
                    "lag_ms_mean": float(np.nanmean(lag_ms)) if np.any(np.isfinite(lag_ms)) else np.nan,
                    "lag_peak_corr_median": float(np.nanmedian(lag_peak_corr)) if np.any(np.isfinite(lag_peak_corr)) else np.nan,
                    "n_rejected_trials": int(len(qc["reject_idx"])),
                    "status": "ok",
                    "error": "",
                }
            )
            print(f"[OK] {sig.subject} :: clean={len(ep_clean.trial_info)} units(A/H)={len(ua)}/{len(uh)}")

        except Exception as exc:
            rows.append(
                {
                    "subject": "",
                    "nwb_file": str(nwb_path),
                    "n_trials": np.nan,
                    "n_clean_trials": np.nan,
                    "n_units_total": np.nan,
                    "n_units_a": np.nan,
                    "n_units_h": np.nan,
                    "n_ch_a": np.nan,
                    "n_ch_h": np.nan,
                    "rho_aa_median": np.nan,
                    "rho_hh_median": np.nan,
                    "rho_ah_median": np.nan,
                    "rho_ha_median": np.nan,
                    "sig_aa_ratio": np.nan,
                    "sig_hh_ratio": np.nan,
                    "sig_ah_ratio": np.nan,
                    "sig_ha_ratio": np.nan,
                    "lag_ms_median": np.nan,
                    "lag_ms_mean": np.nan,
                    "lag_peak_corr_median": np.nan,
                    "n_rejected_trials": np.nan,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"[FAIL] {nwb_path} :: {exc}")

    summary = pd.DataFrame(rows)
    summary_path = args.output_dir / "spike_region_batch_summary.csv"
    summary.to_csv(summary_path, index=False)

    ok_n = int((summary["status"] == "ok").sum()) if len(summary) else 0
    fail_n = int((summary["status"] == "failed").sum()) if len(summary) else 0
    print("saved", summary_path)
    print("ok", ok_n, "failed", fail_n)


if __name__ == "__main__":
    main()
