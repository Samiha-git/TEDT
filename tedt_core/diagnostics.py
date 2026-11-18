"""Engine 1 - exam / curriculum diagnostics with the revised Bloom taxonomy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BLOOM_LEVELS

BLOOM_KEYS = [b[0] for b in BLOOM_LEVELS]


def bloom_distribution(items: pd.DataFrame, weight_col: str | None = "points") -> pd.Series:
    """Share of exam points (or item count) at each Bloom level; always returns all 6 levels."""
    if weight_col and weight_col in items:
        s = items.groupby("bloom_level")[weight_col].sum()
    else:
        s = items.groupby("bloom_level").size()
    s = s.reindex(BLOOM_KEYS).fillna(0.0)
    tot = s.sum()
    return s / tot if tot else s


def curriculum_distribution(curr: pd.DataFrame) -> pd.Series:
    s = curr.groupby("bloom_level")["weight"].sum().reindex(BLOOM_KEYS).fillna(0.0)
    return s / s.sum()


def alignment_index(p_exam: pd.Series, p_curr: pd.Series) -> float:
    """Distributional overlap between exam and curriculum Bloom profiles: 1 - total variation distance.
    1 = identical profiles, 0 = disjoint. It measures *cognitive-level* alignment only, not content coverage."""
    p, q = np.asarray(p_exam, float), np.asarray(p_curr, float)
    return float(1.0 - 0.5 * np.abs(p - q).sum())


def cognitive_demand(p: pd.Series) -> float:
    """Mean Bloom level (1 = remember ... 6 = create) weighted by the distribution."""
    return float((np.asarray(p, float) * np.arange(1, 7)).sum())
