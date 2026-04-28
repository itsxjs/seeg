"""
Run spectral Granger Causality (sGC) on arousal-annotated time segments across all subjects.

This script:
1. Reads arousal_segments.csv and converts to standard event format
2. Iterates through NWB files in a directory
3. For each subject, runs standard connectivity analysis (coherence + sGC)
   with arousal-based events instead of original events
4. Saves results per subject and a combined summary

Usage:
    python run_sgc_on_arousal_segments.py \
        --arousal-csv results/arousal_short_local_3b_fix_full/arousal_segments.csv \
        --data-dir data/000623 \
        --output-dir results/sgc_arousal_all_subjects \
        --device auto
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import savemat

from ah_pipeline.config import PipelineConfig
from ah_pipeline.connectivity_stats import compute_band_coherence, compute_band_granger
from ah_pipeline.nwb_io import iter_nwb_files, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc


def _progress_bar(current: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "] 0/0"
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    pct = 100.0 * current / total
    return f"[{bar}] {current}/{total} ({pct:5.1f}%)"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run sGC + coherence on arousal-annotated segments across all subjects"
    )
    p.add_argument(
        "--arousal-csv",
        type=Path,
        required=True,
        help="Path to arousal_segments.csv from annotate_short_arousal_segments.py",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing NWB files (will recursively search for .nwb)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for sGC results",
    )
    p.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device for preprocessing (auto/cpu/cuda/mps)",
    )
    return p.parse_args()


def main() -> None:
    warnings.filterwarnings("ignore", message=".*verbose is deprecated.*")
    warnings.filterwarnings("ignore", message=".*covariance of constraints does not have full rank.*")

    args = parse_args()

    # Validate inputs
    if not args.arousal_csv.exists():
        raise FileNotFoundError(f"arousal_csv not found: {args.arousal_csv}")
    if not args.data_dir.exists():
        raise FileNotFoundError(f"data_dir not found: {args.data_dir}")

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Read arousal segments and convert to event format
    arousal_df = pd.read_csv(args.arousal_csv)
    print(f"Loaded {len(arousal_df)} arousal segments from {args.arousal_csv}")

    # Create temporary events file with arousal-based onsets
    # Use center_sec as onset, assign to a dummy subject (will be overridden)
    # In the pipeline, we'll duplicate this for each actual subject
    test_events = pd.DataFrame({
        "subject": ["dummy"],  # Will be replaced for each subject
        "onset": [arousal_df["center_sec"].iloc[0]],
        "valence": ["neutral"],
        "event_type": ["arousal_segment"]
    })
    events_csv = args.output_dir / "arousal_events.csv"
    test_events.to_csv(events_csv, index=False)
    print(f"Created template events CSV: {events_csv}")

    # Get NWB files
    nwb_files = list(args.data_dir.rglob("*.nwb"))
    nwb_files = [f for f in nwb_files if "behavior+ecephys" in f.name]
    print(f"Found {len(nwb_files)} NWB files")

    if not nwb_files:
        raise ValueError(f"No *behavior+ecephys*.nwb files found in {args.data_dir}")

    # Configuration
    cfg = PipelineConfig(
        data_dir=args.data_dir,
        event_csv=events_csv,
        output_dir=args.output_dir,
    )

    out_dir = args.output_dir / "connectivity_arousal"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_coh: list[pd.DataFrame] = []
    all_sgc: list[pd.DataFrame] = []
    ok_count = 0
    fail_count = 0

    print("\n" + "=" * 60)
    print("Processing NWB files with arousal-based events")
    print("=" * 60 + "\n")

    for idx, nwb_path in enumerate(nwb_files, start=1):
        run_id = nwb_path.stem.lower()
        subject = run_id.split("_")[0]  # Extract subject ID
        print(f"{_progress_bar(idx - 1, len(nwb_files))} running {run_id}", flush=True)

        try:
            # Load LFP
            sig = load_subject_lfp_from_nwb(nwb_path)
            sig_pp = preprocess_signal(sig, cfg)

            # Create events for this subject using arousal-based onsets
            events_arousal = arousal_df[["center_sec"]].copy()
            events_arousal.rename(columns={"center_sec": "onset"}, inplace=True)
            events_arousal["subject"] = subject
            events_arousal["valence"] = "neutral"
            events_arousal["event_type"] = "arousal_segment"

            # Reorder columns to match pipeline expectation
            events_arousal = events_arousal[["subject", "onset", "valence", "event_type"]]

            # Epoch subject
            ep = epoch_subject(sig_pp, events_arousal, cfg)

            # Run QC
            ep_clean, _ = run_hybrid_qc(ep, cfg)

            # Compute connectivity
            coh_df = compute_band_coherence(ep_clean, sig_pp.region, cfg)
            sgc_df = compute_band_granger(ep_clean, sig_pp.region, cfg)

            # Handle empty results
            if coh_df.empty:
                coh_df = pd.DataFrame(columns=["subject", "trial", "pair", "band", "A_H_coherence", "valence"])
            else:
                coh_df = coh_df.reindex(columns=["subject", "trial", "pair", "band", "A_H_coherence", "valence"])

            if sgc_df.empty:
                sgc_df = pd.DataFrame(columns=["subject", "trial", "pair", "band", "A_to_H_gc", "H_to_A_gc", "valence"])
            else:
                sgc_df = sgc_df.reindex(columns=["subject", "trial", "pair", "band", "A_to_H_gc", "H_to_A_gc", "valence"])

            # Save per-subject
            coh_df.to_csv(out_dir / f"{run_id}_arousal_coherence.csv", index=False)
            sgc_df.to_csv(out_dir / f"{run_id}_arousal_sgc.csv", index=False)

            # Combine
            all_coh.append(coh_df)
            all_sgc.append(sgc_df)
            ok_count += 1

            n_trials = len(ep_clean.trial_info) if ep_clean.data.shape[0] > 0 else 0
            print(f"{_progress_bar(idx, len(nwb_files))} OK: {run_id} ({n_trials} trials, coh={len(coh_df)}, sgc={len(sgc_df)})")

        except Exception as e:
            fail_count += 1
            print(f"{_progress_bar(idx, len(nwb_files))} ERROR: {run_id}: {e}")

    # Combine and save results
    print(f"\n{_progress_bar(len(nwb_files), len(nwb_files))} Done processing")

    if all_coh or all_sgc:
        if all_coh:
            combined_coh = pd.concat(all_coh, ignore_index=True)
            coh_csv = args.output_dir / "combined_arousal_coherence.csv"
            combined_coh.to_csv(coh_csv, index=False)
            print(f"\nSaved combined coherence: {coh_csv} ({len(combined_coh)} rows)")

        if all_sgc:
            combined_sgc = pd.concat(all_sgc, ignore_index=True)
            sgc_csv = args.output_dir / "combined_arousal_sgc.csv"
            combined_sgc.to_csv(sgc_csv, index=False)
            print(f"Saved combined sGC: {sgc_csv} ({len(combined_sgc)} rows)")

            # Summary statistics
            summary = {
                "n_subjects": len(nwb_files),
                "n_success": ok_count,
                "n_failed": fail_count,
                "n_arousal_segments": len(arousal_df),
                "n_bands": int(len(combined_sgc["band"].unique())) if "band" in combined_sgc.columns else 0,
                "n_pairs": int(len(combined_sgc["pair"].unique())) if "pair" in combined_sgc.columns else 0,
                "mean_a_to_h_gc": float(combined_sgc["A_to_H_gc"].mean()) if "A_to_H_gc" in combined_sgc.columns else np.nan,
                "mean_h_to_a_gc": float(combined_sgc["H_to_A_gc"].mean()) if "H_to_A_gc" in combined_sgc.columns else np.nan,
                "sgc_rows": len(combined_sgc),
            }

            if all_coh:
                summary["coh_rows"] = len(combined_coh)
                summary["mean_coherence"] = float(combined_coh["A_H_coherence"].mean())

            summary_json = args.output_dir / "arousal_connectivity_summary.json"
            import json
            with open(summary_json, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"Saved summary: {summary_json}")

            # Save MATLAB format
            mat_file = args.output_dir / "arousal_connectivity_results.mat"
            mat_dict = {
                "sgc_table": combined_sgc.to_records(index=False),
                "arousal_segments": arousal_df.to_records(index=False),
            }
            if all_coh:
                mat_dict["coherence_table"] = combined_coh.to_records(index=False)
            savemat(mat_file, mat_dict, do_compression=True)
            print(f"Saved MATLAB format: {mat_file}")

    else:
        print("ERROR: No successful computations!")
        return

    print("\n" + "=" * 60)
    print("sGC + Coherence on arousal segments COMPLETE")
    print(f"Output directory: {args.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
