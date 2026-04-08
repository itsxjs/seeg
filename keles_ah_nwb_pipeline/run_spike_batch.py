from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

from ah_pipeline.config import PipelineConfig
from ah_pipeline.nwb_io import iter_nwb_files, load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from ah_pipeline.spikes import ifr_hgamma_coupling


def _load_units_table(nwb_path: Path) -> pd.DataFrame:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            return pd.DataFrame({"spike_times": []})
        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            return pd.DataFrame({"spike_times": []})
        return units[["spike_times"]].copy()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch spike analysis for Keles NWB dataset")
    p.add_argument("--data-dir", type=Path, required=True, help="Directory containing NWB files")
    p.add_argument("--event-csv", type=Path, required=True, help="CSV with subject/onset/valence/event_type")
    p.add_argument("--output-dir", type=Path, required=True, help="Where to save per-subject and summary outputs")
    p.add_argument("--max-files", type=int, default=0, help="Optional cap for quick runs; 0 means all")
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

            units_df = _load_units_table(nwb_path)
            spike_res = ifr_hgamma_coupling(units_df, ep_clean, cfg)

            subject_slug = sig.subject.replace("/", "_")
            coupling_path = args.output_dir / f"{subject_slug}_spike_coupling.csv"
            coupling_df = spike_res.coupling.copy()
            if "trial" in coupling_df.columns:
                coupling_df = coupling_df.sort_values(["trial"]).reset_index(drop=True)
            coupling_df.to_csv(coupling_path, index=False)

            np.savez_compressed(
                args.output_dir / f"{subject_slug}_spike_ifr_psth.npz",
                ifr=spike_res.ifr,
                ifr_times=spike_res.ifr_times,
                psth_negative=spike_res.psth.get("negative", np.array([], dtype=float)),
                psth_neutral=spike_res.psth.get("neutral", np.array([], dtype=float)),
                psth_positive=spike_res.psth.get("positive", np.array([], dtype=float)),
            )

            rows.append(
                {
                    "subject": sig.subject,
                    "nwb_file": str(nwb_path),
                    "n_trials": int(len(ep.trial_info)),
                    "n_clean_trials": int(len(ep_clean.trial_info)),
                    "n_units": int(len(units_df)),
                    "ifr_mean": float(np.nanmean(spike_res.ifr)) if spike_res.ifr.size else np.nan,
                    "ifr_peak": float(np.nanmax(spike_res.ifr)) if spike_res.ifr.size else np.nan,
                    "rho_mean": float(np.nanmean(spike_res.coupling["spearman_rho"])) if len(spike_res.coupling) else np.nan,
                    "rho_median": float(np.nanmedian(spike_res.coupling["spearman_rho"])) if len(spike_res.coupling) else np.nan,
                    "p_lt_0_05_ratio": float(np.mean(spike_res.coupling["p_value"] < 0.05)) if len(spike_res.coupling) else np.nan,
                    "n_rejected_trials": int(len(qc["reject_idx"])),
                    "status": "ok",
                    "error": "",
                }
            )
            print(f"[OK] {sig.subject} :: clean_trials={len(ep_clean.trial_info)} units={len(units_df)}")

        except Exception as exc:
            rows.append(
                {
                    "subject": "",
                    "nwb_file": str(nwb_path),
                    "n_trials": np.nan,
                    "n_clean_trials": np.nan,
                    "n_units": np.nan,
                    "ifr_mean": np.nan,
                    "ifr_peak": np.nan,
                    "rho_mean": np.nan,
                    "rho_median": np.nan,
                    "p_lt_0_05_ratio": np.nan,
                    "n_rejected_trials": np.nan,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"[FAIL] {nwb_path} :: {exc}")

    summary = pd.DataFrame(rows)
    summary_path = args.output_dir / "spike_batch_summary.csv"
    summary.to_csv(summary_path, index=False)

    ok_n = int((summary["status"] == "ok").sum()) if len(summary) else 0
    fail_n = int((summary["status"] == "failed").sum()) if len(summary) else 0
    print("saved", summary_path)
    print("ok", ok_n, "failed", fail_n)


if __name__ == "__main__":
    main()
