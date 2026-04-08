from __future__ import annotations

import argparse
from pathlib import Path

from ah_pipeline.config import PipelineConfig
from ah_pipeline.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A-H NWB pipeline for Keles et al. 2024")
    p.add_argument("--data-dir", type=Path, required=True, help="Directory containing .nwb files")
    p.add_argument("--event-csv", type=Path, required=True, help="CSV with columns: subject,onset,valence,event_type")
    p.add_argument("--output-dir", type=Path, required=True, help="Output directory for .mat results")
    p.add_argument("--n-perm", type=int, default=1000, help="Permutation count for CBPT")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = PipelineConfig(
        data_dir=args.data_dir,
        event_csv=args.event_csv,
        output_dir=args.output_dir,
        n_permutations=args.n_perm,
    )
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
