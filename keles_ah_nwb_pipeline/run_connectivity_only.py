from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import pandas as pd
from scipy.io import savemat

from ah_pipeline.config import PipelineConfig
from ah_pipeline.connectivity_stats import compute_band_coherence, compute_band_granger
from ah_pipeline.nwb_io import iter_nwb_files, load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc


COH_COLUMNS = ["subject", "trial", "pair", "band", "A_H_coherence", "valence"]
SGC_COLUMNS = ["subject", "trial", "pair", "band", "A_to_H_gc", "H_to_A_gc", "valence"]


def _progress_bar(current: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "] 0/0"
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    pct = 100.0 * current / total
    return f"[{bar}] {current}/{total} ({pct:5.1f}%)"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run A-H connectivity only (coherence + sGC)")
    p.add_argument("--data-dir", type=Path, required=True, help="Directory containing NWB files")
    p.add_argument("--event-csv", type=Path, required=True, help="Event CSV: subject,onset,valence,event_type")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    return p.parse_args()


def main() -> None:
    warnings.filterwarnings("ignore", message=".*verbose is deprecated since functions should not print results.*")
    warnings.filterwarnings("ignore", message=".*covariance of constraints does not have full rank.*")

    args = parse_args()
    cfg = PipelineConfig(
        data_dir=args.data_dir,
        event_csv=args.event_csv,
        output_dir=args.output_dir,
    )

    events = load_events(cfg.event_csv)
    nwb_files = iter_nwb_files(cfg.data_dir)
    if not nwb_files:
        raise ValueError(f"No .nwb files found in {cfg.data_dir}")
    print(f"found {len(nwb_files)} NWB files")

    out_dir = cfg.output_dir / "connectivity_only"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_coh: list[pd.DataFrame] = []
    all_sgc: list[pd.DataFrame] = []
    ok_count = 0
    fail_count = 0
    skip_count = 0

    for idx, nwb_path in enumerate(nwb_files, start=1):
        run_id = nwb_path.stem.lower()
        print(f"{_progress_bar(idx - 1, len(nwb_files))} running {run_id}", flush=True)
        try:
            sig = load_subject_lfp_from_nwb(nwb_path)
            sig_pp = preprocess_signal(sig, cfg)
            ep = epoch_subject(sig_pp, events, cfg)
            ep_clean, _ = run_hybrid_qc(ep, cfg)

            coh_df = compute_band_coherence(ep_clean, sig_pp.region, cfg)
            sgc_df = compute_band_granger(ep_clean, sig_pp.region, cfg)

            if coh_df.empty:
                coh_df = pd.DataFrame(columns=COH_COLUMNS)
            else:
                coh_df = coh_df.reindex(columns=COH_COLUMNS)
            if sgc_df.empty:
                sgc_df = pd.DataFrame(columns=SGC_COLUMNS)
            else:
                sgc_df = sgc_df.reindex(columns=SGC_COLUMNS)

            coh_df.to_csv(out_dir / f"{run_id}_AH_coherence.csv", index=False)
            sgc_df.to_csv(out_dir / f"{run_id}_sGC.csv", index=False)

            if coh_df.empty and sgc_df.empty:
                skip_count += 1
                print(f"{_progress_bar(idx, len(nwb_files))} skipped {run_id}: empty coherence & sGC")
                continue

            savemat(
                out_dir / f"{run_id}_connectivity_only.mat",
                {
                    "AH_coherence_table": coh_df.to_records(index=False),
                    "sGC_table": sgc_df.to_records(index=False),
                },
                do_compression=True,
            )

            all_coh.append(coh_df)
            all_sgc.append(sgc_df)
            ok_count += 1
            print(
                f"{_progress_bar(idx, len(nwb_files))} done {sig.subject}: "
                f"coherence_rows={len(coh_df)} sgc_rows={len(sgc_df)}"
            )
        except Exception as exc:
            fail_count += 1
            print(f"{_progress_bar(idx, len(nwb_files))} failed {run_id}: {exc}")

    if all_coh:
        pd.concat(all_coh, ignore_index=True).to_csv(out_dir / "all_subjects_AH_coherence.csv", index=False)
    else:
        pd.DataFrame(columns=COH_COLUMNS).to_csv(out_dir / "all_subjects_AH_coherence.csv", index=False)

    if all_sgc:
        pd.concat(all_sgc, ignore_index=True).to_csv(out_dir / "all_subjects_sGC.csv", index=False)
    else:
        pd.DataFrame(columns=SGC_COLUMNS).to_csv(out_dir / "all_subjects_sGC.csv", index=False)

    print(f"summary: ok={ok_count} skipped={skip_count} failed={fail_count}")
    print("saved", out_dir)


if __name__ == "__main__":
    main()
