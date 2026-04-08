from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass(slots=True)
class PipelineConfig:
    data_dir: Path
    output_dir: Path
    event_csv: Path | None = None
    target_sfreq: float = 1000.0
    l_freq: float = 1.0
    h_freq: float = 200.0
    notch_freq: float = 50.0
    epoch_tmin: float = -0.5
    epoch_tmax: float = 2.0
    baseline_tmin: float = -0.5
    baseline_tmax: float = 0.0
    analysis_tmin: float = 0.0
    analysis_tmax: float = 2.0
    qc_thr_z: float = 4.0
    qc_vote_robust: int = 5
    qc_abs_uV: float = 200.0
    qc_sigma_p2p: float = 3.0
    qc_vote_sigma: int = 3
    tf_freqs: np.ndarray = field(default_factory=lambda: np.logspace(np.log10(2), np.log10(120), 24))
    tf_n_cycles: np.ndarray = field(default_factory=lambda: np.logspace(np.log10(3), np.log10(12), 24))
    tf_bootstrap_n: int = 1000
    tf_bin_ms: float = 50.0
    hgamma_low: float = 70.0
    hgamma_high: float = 150.0
    ifr_bin_ms: float = 10.0
    ifr_gauss_ms: float = 50.0
    n_permutations: int = 1000
    random_seed: int = 42


AMY_KEYWORDS: Sequence[str] = ("amyg", "amygdala")
HIPP_KEYWORDS: Sequence[str] = ("hip", "hipp", "hippocampus")
