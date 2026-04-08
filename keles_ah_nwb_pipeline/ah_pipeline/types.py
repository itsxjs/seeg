from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SubjectSignals:
    subject: str
    sfreq: float
    data: np.ndarray
    channel_names: list[str]
    region: list[str]


@dataclass(slots=True)
class EpochData:
    subject: str
    sfreq: float
    times: np.ndarray
    data: np.ndarray
    channel_names: list[str]
    trial_info: pd.DataFrame


@dataclass(slots=True)
class TimeFrequencyResult:
    z_power_ds: np.ndarray
    freqs: np.ndarray
    times_ds: np.ndarray
    cond_mean_z: dict[str, np.ndarray]


@dataclass(slots=True)
class SpikeResult:
    ifr: np.ndarray
    ifr_times: np.ndarray
    psth: dict[str, np.ndarray]
    coupling: pd.DataFrame
