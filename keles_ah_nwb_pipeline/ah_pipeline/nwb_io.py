from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

from .config import AMY_KEYWORDS, HIPP_KEYWORDS
from .types import SubjectSignals


def _infer_subject_id(nwb_path: Path) -> str:
    m_bids = re.search(r"(sub-[A-Za-z0-9]+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_bids:
        return m_bids.group(1).lower()
    m_num = re.search(r"(sub\d+)", nwb_path.stem, flags=re.IGNORECASE)
    if m_num:
        return m_num.group(1).lower()
    return nwb_path.stem.lower()


def _region_from_label(label: str) -> str:
    low = (label or "").lower()
    if any(key in low for key in AMY_KEYWORDS):
        return "amygdala"
    if any(key in low for key in HIPP_KEYWORDS):
        return "hippocampus"
    return "other"


def _build_bipolar_pairs(ch_names: list[str], regions: list[str]) -> list[tuple[int, int, str, str]]:
    pairs: list[tuple[int, int, str, str]] = []
    grouped: dict[str, list[tuple[int, str, str, int]]] = {}
    for idx, (name, region) in enumerate(zip(ch_names, regions, strict=True)):
        m = re.match(r"([A-Za-z\-]+)\s*([0-9]+)", name.replace("_", ""))
        if not m:
            continue
        shaft = m.group(1)
        num = int(m.group(2))
        grouped.setdefault(shaft, []).append((idx, name, region, num))

    for entries in grouped.values():
        entries.sort(key=lambda x: x[3])
        for (i1, n1, r1, nidx1), (i2, n2, r2, nidx2) in zip(entries[:-1], entries[1:], strict=False):
            if nidx2 - nidx1 != 1:
                continue
            if r1 != r2 or r1 == "other":
                continue
            pairs.append((i1, i2, f"{n1}-{n2}", r1))
    return pairs


def load_subject_lfp_from_nwb(nwb_path: Path) -> SubjectSignals:
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if "ecephys" not in nwb.processing:
            raise ValueError(f"No ecephys processing module in {nwb_path}")
        ece = nwb.processing["ecephys"]
        lfp = (
            ece.data_interfaces.get("LFP_macro")
            or ece.data_interfaces.get("LFP")
            or ece.data_interfaces.get("LFP_micro")
        )
        if lfp is None:
            lfp_candidates = [v for v in ece.data_interfaces.values() if hasattr(v, "electrical_series")]
            if not lfp_candidates:
                raise ValueError(f"No LFP interface in {nwb_path}")
            lfp = lfp_candidates[0]
        es = next(iter(lfp.electrical_series.values()))

        data = np.asarray(es.data, dtype=np.float32)
        sfreq = float(es.rate)

        elec_indices = np.asarray(es.electrodes.data[:], dtype=int)
        elec_df = nwb.electrodes.to_dataframe().iloc[elec_indices].reset_index(drop=True)
        location = elec_df.get("location", pd.Series([""] * len(elec_df))).fillna("").astype(str)
        labels = elec_df.get(
            "label",
            elec_df.get(
                "origchannel_name",
                elec_df.get("group_name", pd.Series([f"ch{i}" for i in range(len(elec_df))])),
            ),
        ).astype(str)
        regions = [_region_from_label(f"{loc} {lab}") for loc, lab in zip(location, labels, strict=True)]

    keep = [i for i, region in enumerate(regions) if region in {"amygdala", "hippocampus"}]
    if not keep:
        raise ValueError(f"No amygdala/hippocampus electrodes found in {nwb_path}")

    data_keep = data[:, keep].T
    labels_keep = [str(labels.iloc[i]) for i in keep]
    regions_keep = [regions[i] for i in keep]

    pairs = _build_bipolar_pairs(labels_keep, regions_keep)
    if not pairs:
        raise ValueError(f"No adjacent bipolar pairs found in selected channels for {nwb_path}")

    bip_data = np.stack([data_keep[i2] - data_keep[i1] for i1, i2, _, _ in pairs], axis=0)
    bip_names = [name for _, _, name, _ in pairs]
    bip_regions = [region for _, _, _, region in pairs]

    return SubjectSignals(
        subject=_infer_subject_id(nwb_path),
        sfreq=sfreq,
        data=bip_data,
        channel_names=bip_names,
        region=bip_regions,
    )


def iter_nwb_files(data_dir: Path) -> list[Path]:
    nwb_files = sorted(p for p in data_dir.rglob("*.nwb") if not p.name.startswith("._"))
    return nwb_files


def load_events(event_csv: Path | None) -> pd.DataFrame:
    if event_csv is None:
        raise ValueError("event_csv is required. Provide columns: subject,onset,valence,event_type")
    df = pd.read_csv(event_csv)
    required = {"subject", "onset", "valence", "event_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing event columns: {missing}")
    df["subject"] = df["subject"].str.lower()
    return df
