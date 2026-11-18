"""Synthetic-only demonstration dataset for the Lot 1 territorial pilot.

These values are generated solely to demonstrate the pipeline and map interface.
They are not INS observations, not estimates, and not suitable for policy analysis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tedt_core.config import GOVERNORATES


def make_schooling_demo(seed: int = 2031) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for governorate, (name_fr, name_ar) in GOVERNORATES.items():
        rows.append({
            "governorate": governorate,
            "governorate_fr": name_fr,
            "governorate_ar": name_ar,
            "age_band": "6-14",
            "schooling_rate_demo_pct": round(float(rng.uniform(91.0, 99.5)), 1),
            "value_origin": "synthetic_demo_only",
            "source_id": "TEDT-SYNTHETIC-LOT1-DEMO",
            "reference_period": "DEMO_ONLY_NOT_RGPH2024",
        })
    return pd.DataFrame(rows)
