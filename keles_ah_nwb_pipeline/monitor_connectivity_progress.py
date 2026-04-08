from __future__ import annotations

import argparse
import time
from pathlib import Path


def progress_bar(current: int, total: int, width: int = 32) -> str:
    if total <= 0:
        return "[" + "-" * width + "] 0/0"
    filled = int(width * current / total)
    return f"[{'#' * filled}{'-' * (width - filled)}] {current}/{total} ({100*current/total:5.1f}%)"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor run_connectivity_only progress from output files")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True, help="Pipeline root output dir; monitors output-dir/connectivity_only")
    p.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    conn_dir = args.output_dir / "connectivity_only"
    conn_dir.mkdir(parents=True, exist_ok=True)

    total = len([p for p in args.data_dir.rglob("*.nwb") if not p.name.startswith("._")])
    print(f"monitoring: total_nwb={total} in {args.data_dir}")

    while True:
        done = len(list(conn_dir.glob("*_connectivity_only.mat")))
        coh_csv = len(list(conn_dir.glob("*_AH_coherence.csv")))
        sgc_csv = len(list(conn_dir.glob("*_sGC.csv")))

        line = (
            f"\r{progress_bar(done, total)} "
            f"mat={done} coh_csv={coh_csv} sgc_csv={sgc_csv}"
        )
        print(line, end="", flush=True)

        if total > 0 and done >= total:
            print("\ncompleted")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
