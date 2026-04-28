from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.io import savemat

from ah_pipeline.config import PipelineConfig
from ah_pipeline.nwb_io import _infer_subject_id, iter_nwb_files, load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from plot_group_full_spectrum import summarize_full_spectrum_group
from run_full_spectrum_connectivity_one_subject import (
    _pick_region_pairs,
    compute_full_spectral_gc,
    compute_sliding_coherence_full,
    plot_literature_style,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch full-spectrum LFP coherence + spectral GC from NWB")
    p.add_argument("--data-dir", type=Path, required=True, help="Directory containing NWB files")
    p.add_argument("--event-csv", type=Path, required=True, help="Event CSV with subject/onset/valence/event_type")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory for *_fullspectrum.mat/png and group plots")
    p.add_argument("--gc-lags", type=int, default=20, help="GC lag parameter")
    p.add_argument("--win-ms", type=float, default=500.0, help="Sliding coherence window (ms)")
    p.add_argument("--step-ms", type=float, default=10.0, help="Sliding coherence step (ms)")
    p.add_argument("--subwin-ms", type=float, default=250.0, help="Welch sub-window size (ms)")
    p.add_argument("--sub-ovlp", type=float, default=0.5, help="Welch overlap ratio")
    p.add_argument("--max-runs", type=int, default=0, help="Optional cap for quick runs; 0 means all")
    p.add_argument("--first-run-per-subject", action="store_true", help="Only keep the first NWB run per subject")
    p.add_argument("--overwrite", action="store_true", help="Recompute runs even if *_fullspectrum.mat already exists")
    return p.parse_args()


def _first_nwb_per_subject(nwb_files: list[Path]) -> list[Path]:
    by_sub: dict[str, Path] = {}
    first_runs: list[Path] = []
    for p in nwb_files:
        sid = _infer_subject_id(p)
        if sid in by_sub:
            continue
        by_sub[sid] = p
        first_runs.append(p)
    return first_runs


def _collect_nwb_runs(data_dir: Path, first_run_per_subject: bool) -> list[Path]:
    all_nwb = iter_nwb_files(data_dir)
    if first_run_per_subject:
        return _first_nwb_per_subject(all_nwb)
    return all_nwb


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cfg = PipelineConfig(data_dir=args.data_dir, event_csv=args.event_csv, output_dir=args.output_dir)
    _ = load_events(args.event_csv)

    nwb_files = _collect_nwb_runs(args.data_dir, first_run_per_subject=args.first_run_per_subject)
    if args.max_runs > 0:
        nwb_files = nwb_files[: args.max_runs]
    if not nwb_files:
        raise RuntimeError(f"No NWB runs found under {args.data_dir}")

    mats: list[Path] = []
    skipped: list[tuple[str, str]] = []

    print(f"runs_to_process={len(nwb_files)}")

    for i, nwb_path in enumerate(nwb_files, start=1):
        run_id = nwb_path.stem.lower()
        sid = _infer_subject_id(nwb_path)
        base = f"{sid}_{run_id}_fullspectrum"
        out_mat = args.output_dir / f"{base}.mat"
        out_png = args.output_dir / f"{base}.png"

        if out_mat.exists() and not args.overwrite:
            mats.append(out_mat)
            print(f"[{i}/{len(nwb_files)}] {run_id}: reuse existing {out_mat.name}")
            continue

        print(f"[{i}/{len(nwb_files)}] {run_id}: computing full-spectrum", flush=True)
        try:
            subject_sig = load_subject_lfp_from_nwb(nwb_path)
            preprocessed = preprocess_signal(subject_sig, cfg)
            events = load_events(args.event_csv)
            epochs = epoch_subject(preprocessed, events, cfg)
            clean_ep, qc = run_hybrid_qc(epochs, cfg)

            if clean_ep.data.shape[0] == 0:
                skipped.append((run_id, "no clean trials after QC"))
                print(f"  skip {run_id}: no clean trials after QC")
                continue

            pairs, amyg_idx, hip_idx = _pick_region_pairs(clean_ep.channel_names, preprocessed.region)
            if len(amyg_idx) == 0 or len(hip_idx) == 0:
                skipped.append((run_id, "missing amygdala/hippocampus channels"))
                print(f"  skip {run_id}: missing amygdala/hippocampus channels")
                continue

            freqs_coh, time_coh, coh_tf = compute_sliding_coherence_full(
                ep_data=clean_ep.data,
                sfreq=clean_ep.sfreq,
                amyg_idx=amyg_idx,
                hip_idx=hip_idx,
                times=clean_ep.times,
                freq_range=(2.0, 45.0),
                win_ms=args.win_ms,
                step_ms=args.step_ms,
                subwin_ms=args.subwin_ms,
                sub_ovlp=args.sub_ovlp,
            )

            freqs_gc, gc_a2h, gc_h2a = compute_full_spectral_gc(
                ep_data=clean_ep.data,
                sfreq=clean_ep.sfreq,
                amyg_idx=amyg_idx,
                hip_idx=hip_idx,
                fmin=2.0,
                fmax=45.0,
                gc_n_lags=args.gc_lags,
            )

            plot_literature_style(
                freqs_coh=freqs_coh,
                time_coh=time_coh,
                coh_tf=coh_tf,
                freqs_gc=freqs_gc,
                gc_a2h=gc_a2h,
                gc_h2a=gc_h2a,
                subject=sid,
                out_png=out_png,
            )

            savemat(
                out_mat,
                {
                    "subject": sid,
                    "source_nwb": str(nwb_path),
                    "n_trials_clean": int(clean_ep.data.shape[0]),
                    "n_channels": int(clean_ep.data.shape[1]),
                    "n_pairs": int(len(pairs)),
                    "freqs_coh": freqs_coh,
                    "time_coh": time_coh,
                    "coh_tf": coh_tf,
                    "freqs_gc": freqs_gc,
                    "gc_a2h": gc_a2h,
                    "gc_h2a": gc_h2a,
                    "qc_keep_idx": qc["keep_idx"],
                    "qc_reject_idx": qc["reject_idx"],
                },
                do_compression=True,
            )
            mats.append(out_mat)
            print(f"  saved {out_mat.name}")
        except Exception as exc:
            skipped.append((run_id, str(exc)))
            print(f"  skip {run_id}: {exc}")

    summarize_full_spectrum_group(args.output_dir, mats, skipped_runs=[run_id for run_id, _ in skipped])

    summary = args.output_dir / "run_full_spectrum_nwb_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write(f"runs_total={len(nwb_files)}\n")
        f.write(f"runs_used={len(mats)}\n")
        f.write(f"runs_skipped={len(skipped)}\n")
        f.write(f"mode={'first_run_per_subject' if args.first_run_per_subject else 'all_runs'}\n")
        for run_id, reason in skipped:
            f.write(f"  {run_id} :: {reason}\n")

    print(f"used={len(mats)} skipped={len(skipped)}")
    print(f"saved group plots under {args.output_dir}")
    print(f"saved {summary}")


if __name__ == "__main__":
    main()
