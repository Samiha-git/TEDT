"""Explicit missing-data policy shared by analytical and simulation workflows.

Default policy: do not impute. Missing required model inputs block the calculation.
Optional median imputation is available only when explicitly requested and returns
an audit report so callers can disclose the number and share of imputed cells.
"""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class ImputationAudit:
    strategy: str
    cells_imputed: int
    cells_eligible: int
    proportion_imputed: float
    by_column: dict[str, int]


def apply_missing_policy(df: pd.DataFrame, columns: list[str], strategy: str = "none") -> tuple[pd.DataFrame, ImputationAudit]:
    if strategy not in {"none", "median"}:
        raise ValueError("strategy must be 'none' or 'median'")
    out = df.copy(deep=True)
    absent = [c for c in columns if c not in out.columns]
    if absent:
        raise ValueError(f"Required columns absent: {', '.join(absent)}")
    missing = out[columns].isna()
    by_column = {c: int(missing[c].sum()) for c in columns}
    cells = int(missing.to_numpy().sum())
    eligible = int(out[columns].size)
    if strategy == "none" and cells:
        raise ValueError(f"Missing required values block calculation: {cells} cell(s)")
    if strategy == "median":
        for c in columns:
            numeric = pd.to_numeric(out[c], errors="coerce")
            invalid = out[c].notna() & numeric.isna()
            if invalid.any():
                raise ValueError(f"Cannot impute {c}: {int(invalid.sum())} invalid non-numeric value(s)")
            if missing[c].any():
                median = numeric.median()
                if pd.isna(median):
                    raise ValueError(f"Cannot impute {c}: no observed numeric values")
                out[c] = numeric.fillna(median)
    audit = ImputationAudit(strategy, cells if strategy == "median" else 0, eligible,
                            (cells / eligible) if eligible else 0.0,
                            by_column if strategy == "median" else {c: 0 for c in columns})
    return out, audit
