from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.stats import spearmanr, wilcoxon

from ah_pipeline.nwb_io import iter_nwb_files, load_events


def infer_subject_id(nwb_path: Path) -> str:
    m_bids = re.search(r"(sub-[A-Za-z0-9]+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_bids:
        return m_bids.group(1).lower()
    m_num = re.search(r"(sub\d+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_num:
        return m_num.group(1).lower()
    return nwb_path.stem.lower()


def load_unit_spike_times(nwb_path: Path) -> list[np.ndarray]:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            return []
        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            return []
        out: list[np.ndarray] = []
        for st in units["spike_times"].to_list():
            arr = np.asarray(st, dtype=float)
            if arr.size > 0:
                out.append(arr)
            else:
                out.append(np.array([], dtype=float))
        return out


def rates_around_events(
    spike_times: np.ndarray,
    onsets: np.ndarray,
    baseline_win: tuple[float, float],
    response_win: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    b0, b1 = baseline_win
    r0, r1 = response_win
    bdur = b1 - b0
    rdur = r1 - r0
    base = np.zeros(len(onsets), dtype=float)
    resp = np.zeros(len(onsets), dtype=float)
    for i, o in enumerate(onsets):
        nb = np.sum((spike_times >= (o + b0)) & (spike_times < (o + b1)))
        nr = np.sum((spike_times >= (o + r0)) & (spike_times < (o + r1)))
        base[i] = nb / max(bdur, 1e-12)
        resp[i] = nr / max(rdur, 1e-12)
    return base, resp


def classify_unit(base: np.ndarray, resp: np.ndarray, min_effect_hz: float, alpha: float) -> tuple[str, float, float]:
    delta = resp - base
    med_delta = float(np.median(delta)) if delta.size else np.nan

    if delta.size < 6:
        return "uncertain", med_delta, np.nan

    if np.allclose(delta, 0.0):
        p = 1.0
    else:
        try:
            _stat, p = wilcoxon(delta)
            p = float(p)
        except ValueError:
            p = 1.0

    if p < alpha and med_delta >= min_effect_hz:
        return "up", med_delta, p
    if p < alpha and med_delta <= -min_effect_hz:
        return "down", med_delta, p
    return "uncertain", med_delta, p


def session_antagonism_score(unit_delta_trials: list[np.ndarray], labels: list[str]) -> float:
    up_idx = [i for i, lab in enumerate(labels) if lab == "up"]
    dn_idx = [i for i, lab in enumerate(labels) if lab == "down"]
    if not up_idx or not dn_idx:
        return np.nan

    rhos: list[float] = []
    for i in up_idx:
        for j in dn_idx:
            a = unit_delta_trials[i]
            b = unit_delta_trials[j]
            if len(a) != len(b):
                continue
            r, _p = spearmanr(a, b, nan_policy="omit")
            if np.isfinite(r):
                rhos.append(float(r))
    if not rhos:
        return np.nan
    return float(np.median(rhos))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find antagonistic spike cell classes (event-up vs event-down)")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--event-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--baseline", type=float, nargs=2, default=(-0.5, 0.0))
    p.add_argument("--response", type=float, nargs=2, default=(0.0, 1.0))
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--min-effect-hz", type=float, default=0.5)
    p.add_argument("--max-files", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    events = load_events(args.event_csv)
    nwb_files = iter_nwb_files(args.data_dir)
    if args.max_files > 0:
        nwb_files = nwb_files[: args.max_files]

    sess_rows: list[dict[str, object]] = []
    unit_rows: list[dict[str, object]] = []

    for nwb_path in nwb_files:
        subject = infer_subject_id(nwb_path)
        sub_ev = events.loc[events["subject"] == subject].copy()
        if sub_ev.empty:
            sess_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "n_events": 0,
                    "n_units": np.nan,
                    "n_up": np.nan,
                    "n_down": np.nan,
                    "n_uncertain": np.nan,
                    "up_frac": np.nan,
                    "down_frac": np.nan,
                    "has_antagonistic_classes": False,
                    "antagonism_rho_median": np.nan,
                    "status": "failed",
                    "error": "no events",
                }
            )
            print(f"[FAIL] {subject} :: no events")
            continue

        onsets = sub_ev["onset"].astype(float).to_numpy()

        try:
            units = load_unit_spike_times(nwb_path)
            labels: list[str] = []
            deltas_for_score: list[np.ndarray] = []

            for u_idx, st in enumerate(units):
                base, resp = rates_around_events(
                    spike_times=st,
                    onsets=onsets,
                    baseline_win=(float(args.baseline[0]), float(args.baseline[1])),
                    response_win=(float(args.response[0]), float(args.response[1])),
                )
                label, med_delta, p = classify_unit(base, resp, float(args.min_effect_hz), float(args.alpha))
                labels.append(label)
                deltas_for_score.append(resp - base)

                unit_rows.append(
                    {
                        "subject": subject,
                        "nwb_file": str(nwb_path),
                        "unit_index": int(u_idx),
                        "n_events": int(len(onsets)),
                        "baseline_rate_mean": float(np.mean(base)) if len(base) else np.nan,
                        "response_rate_mean": float(np.mean(resp)) if len(resp) else np.nan,
                        "delta_rate_median": float(med_delta),
                        "p_value": float(p) if np.isfinite(p) else np.nan,
                        "class": label,
                    }
                )

            n_up = int(sum(1 for x in labels if x == "up"))
            n_down = int(sum(1 for x in labels if x == "down"))
            n_uncertain = int(sum(1 for x in labels if x == "uncertain"))
            n_units = int(len(labels))
            has_ant = n_up > 0 and n_down > 0
            ant_rho = session_antagonism_score(deltas_for_score, labels)

            sess_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "n_events": int(len(onsets)),
                    "n_units": n_units,
                    "n_up": n_up,
                    "n_down": n_down,
                    "n_uncertain": n_uncertain,
                    "up_frac": float(n_up / n_units) if n_units else np.nan,
                    "down_frac": float(n_down / n_units) if n_units else np.nan,
                    "has_antagonistic_classes": bool(has_ant),
                    "antagonism_rho_median": float(ant_rho) if np.isfinite(ant_rho) else np.nan,
                    "status": "ok",
                    "error": "",
                }
            )
            print(f"[OK] {subject} :: units={n_units} up/down={n_up}/{n_down} ant={has_ant}")

        except Exception as exc:
            sess_rows.append(
                {
                    "subject": subject,
                    "nwb_file": str(nwb_path),
                    "n_events": int(len(onsets)),
                    "n_units": np.nan,
                    "n_up": np.nan,
                    "n_down": np.nan,
                    "n_uncertain": np.nan,
                    "up_frac": np.nan,
                    "down_frac": np.nan,
                    "has_antagonistic_classes": False,
                    "antagonism_rho_median": np.nan,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"[FAIL] {subject} :: {exc}")

    sess_df = pd.DataFrame(sess_rows)
    unit_df = pd.DataFrame(unit_rows)
    sess_path = args.output_dir / "antagonistic_cells_session_summary.csv"
    unit_path = args.output_dir / "antagonistic_cells_unit_table.csv"
    sess_df.to_csv(sess_path, index=False)
    unit_df.to_csv(unit_path, index=False)

    ok_n = int((sess_df["status"] == "ok").sum()) if len(sess_df) else 0
    ant_n = int(sess_df["has_antagonistic_classes"].fillna(False).sum()) if len(sess_df) else 0
    print("saved", sess_path)
    print("saved", unit_path)
    print("ok_sessions", ok_n, "antagonistic_sessions", ant_n)


if __name__ == "__main__":
    main()
