"""Shared indicator calculations with explicit missing-value semantics.

weighted_mean uses pairwise complete observations only (no replacement by zero or
mean). Distributional measures require complete finite vectors and fail otherwise.
"""
from __future__ import annotations

import numpy as np


def _paired(values, weights=None):
    v = np.asarray(values, dtype=float)
    w = np.ones_like(v) if weights is None else np.asarray(weights, dtype=float)
    if v.shape != w.shape:
        raise ValueError("values and weights must have identical shapes")
    valid = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return v[valid], w[valid]


def weighted_mean(values, weights) -> float:
    v, w = _paired(values, weights)
    if not len(v) or w.sum() <= 0:
        return float("nan")
    return float(np.dot(v, w) / w.sum())


def _complete(values, weights=None):
    v = np.asarray(values, dtype=float)
    w = np.ones_like(v) if weights is None else np.asarray(weights, dtype=float)
    if v.shape != w.shape or v.ndim != 1:
        raise ValueError("values and weights must be one-dimensional arrays of equal length")
    if not np.isfinite(v).all() or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("Distributional indicators require complete finite values and positive weights")
    return v, w


def weighted_gini(values, weights=None) -> float:
    """Gini coefficient with population weights (0 = perfect equality). Values must be >= 0."""
    v, w = _complete(values, weights)
    if (v < 0).any():
        raise ValueError("Gini values must be non-negative")
    order = np.argsort(v)
    v, w = v[order], w[order]
    cw = np.cumsum(w)
    total_w = cw[-1]
    total_value = (v * w).sum()
    if total_value == 0:
        return 0.0
    cum_share_pop = np.concatenate([[0.0], cw / total_w])
    cum_share_val = np.concatenate([[0.0], np.cumsum(v * w) / total_value])
    area = np.trapezoid(cum_share_val, cum_share_pop)
    return float(1.0 - 2.0 * area)


def lorenz_curve(values, weights=None):
    v, w = _complete(values, weights)
    if (v < 0).any() or (v * w).sum() <= 0:
        raise ValueError("Lorenz curve requires non-negative values with a positive total")
    order = np.argsort(v)
    v, w = v[order], w[order]
    x = np.concatenate([[0.0], np.cumsum(w) / w.sum()])
    y = np.concatenate([[0.0], np.cumsum(v * w) / (v * w).sum()])
    return x, y


def weighted_cv(values, weights=None) -> float:
    v, w = _complete(values, weights)
    m = weighted_mean(v, w)
    if m == 0:
        return 0.0
    var = (w * (v - m) ** 2).sum() / w.sum()
    return float(np.sqrt(var) / abs(m))


def top_bottom_gap(values, weights, share: float = 0.25) -> float:
    """Difference between weighted means of top and bottom population shares."""
    v, w = _complete(values, weights)
    if not 0 < share <= 0.5:
        raise ValueError("share must be in (0, 0.5]")
    order = np.argsort(v)
    v, w = v[order], w[order]
    cw = np.cumsum(w) / w.sum()

    def group_mean(mask_weights):
        denom = mask_weights.sum()
        return float((v * mask_weights).sum() / denom) if denom > 0 else float("nan")

    prev = np.concatenate([[0.0], cw[:-1]])
    span = cw - prev
    safe = np.where(span > 0, span, 1.0)
    low_frac = np.clip(np.minimum(cw, share) - np.minimum(prev, share), 0, None) / safe
    top_lo = 1.0 - share
    high_frac = np.clip(np.maximum(cw, top_lo) - np.maximum(prev, top_lo), 0, None) / safe
    return group_mean(high_frac * w) - group_mean(low_frac * w)
