"""Synthetic (simulated) datasets. NOTHING here is an official statistic.

The generator is calibrated only to the *order of magnitude* of the national aggregates published
for 2026-2027 (see config.REFERENCE_AGGREGATES). Governorate-level values are random draws.
Documented generator assumptions (they are assumptions, not findings):
  * a latent "deprivation" factor per governorate lowers quality, equipment and raises drop-out;
  * no geographic pattern is imposed: which governorate is more or less deprived is random.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    BLOOM_LEVELS,
    GOVERNORATES,
    REFERENCE_AGGREGATES as REF,
    SUBJECTS,
    SYNTHETIC_SEED,
)

YEARS = list(range(2018, 2026))
KEYS = list(GOVERNORATES)


def make_context(seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(KEYS)
    weight = rng.lognormal(0, 0.55, n)
    weight /= weight.sum()
    deprivation = np.clip(rng.beta(2.0, 2.2, n), 0.02, 0.98)
    crowding = rng.normal(0, 1, n)
    rural = np.clip(0.25 + 0.55 * deprivation + rng.normal(0, 0.08, n), 0.05, 0.95)
    base_quality = 58 - 16 * deprivation + rng.normal(0, 2, n)
    return pd.DataFrame(
        {
            "governorate": KEYS,
            "weight": weight,
            "deprivation_index": deprivation.round(3),
            "crowding_z": crowding,
            "rural_share": rural.round(3),
            "base_quality": base_quality,
        }
    )


def make_institutions(ctx: pd.DataFrame, geo_centroids: dict[str, tuple[float, float]], seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    ctx_i = ctx.set_index("governorate")
    frames = []
    spec = [
        ("primary", REF["institutions_primary"], REF["pupils_primary"], REF["teachers_primary"], REF["classes_primary"]),
        ("secondary", REF["institutions_secondary"], REF["pupils_secondary"], REF["teachers_secondary"], REF["classes_secondary"]),
    ]
    for level, n, tot_pupils, tot_teachers, tot_classes in spec:
        g_idx = rng.choice(len(KEYS), size=n, p=ctx["weight"].to_numpy())
        gk = np.array(KEYS)[g_idx]
        dep = ctx_i.loc[gk, "deprivation_index"].to_numpy()
        crowd = ctx_i.loc[gk, "crowding_z"].to_numpy()
        base_q = ctx_i.loc[gk, "base_quality"].to_numpy()
        classes = np.maximum(2, rng.gamma(3.0, (tot_classes / n) / 3.0, n))
        mean_cs = tot_pupils / tot_classes
        class_size = mean_cs * (1 + 0.10 * crowd) * rng.lognormal(0, 0.10, n)
        pupils = classes * class_size
        tpc = tot_teachers / tot_classes
        teachers = classes * tpc * rng.lognormal(0, 0.08, n)
        # rescale to the published order of magnitude
        pupils *= tot_pupils / pupils.sum()
        teachers *= tot_teachers / teachers.sum()
        classes *= tot_classes / classes.sum()
        mean_eq = np.clip(0.75 - 0.35 * dep, 0.15, 0.9)
        k = 12.0
        equip = rng.beta(mean_eq * k, (1 - mean_eq) * k)
        score = np.clip(base_q + rng.normal(0, 6, n), 5, 98)
        logit = (-4.2 + 2.0 * dep) if level == "primary" else (-2.6 + 1.8 * dep)
        dropout = 1 / (1 + np.exp(-(logit + rng.normal(0, 0.35, n))))
        lat = np.array([geo_centroids[k][0] for k in gk]) + rng.normal(0, 0.09, n)
        lon = np.array([geo_centroids[k][1] for k in gk]) + rng.normal(0, 0.09, n)
        frames.append(
            pd.DataFrame(
                {
                    "institution_id": [f"SYN-{level[:3].upper()}-{i:05d}" for i in range(n)],
                    "governorate": gk,
                    "level": level,
                    "pupils": np.maximum(10, pupils.round()).astype(int),
                    "teachers": np.maximum(1, teachers.round()).astype(int),
                    "classes": np.maximum(1, classes.round()).astype(int),
                    "equipment_index": equip.round(3),
                    "mean_score": score.round(1),
                    "dropout_rate": dropout.round(4),
                    "lat": lat.round(4),
                    "lon": lon.round(4),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_results(ctx: pd.DataFrame, seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 2)
    subj_eff = {"arabic": 1.5, "french": -3.0, "math": -4.5, "science": -1.0}
    level_eff = {"primary": 4.0, "secondary": -2.0}
    trend_g = {k: rng.normal(0.25, 0.30) for k in KEYS}
    year_eff = {y: rng.normal(0, 0.9) for y in YEARS}
    rows = []
    for _, c in ctx.iterrows():
        for y in YEARS:
            for level in ("primary", "secondary"):
                for sub in SUBJECTS:
                    score = (
                        c["base_quality"] + subj_eff[sub] + level_eff[level]
                        + trend_g[c["governorate"]] * (y - YEARS[0]) + year_eff[y] + rng.normal(0, 1.5)
                    )
                    score = float(np.clip(score, 5, 98))
                    pass_rate = 1 / (1 + np.exp(-(score - 50) / 8))
                    candidate_count = int(rng.integers(1500, 9000))
                    rows.append((c["governorate"], y, level, sub, round(score, 2), round(pass_rate, 4), candidate_count))
    return pd.DataFrame(rows, columns=["governorate", "year", "level", "subject", "mean_score", "pass_rate", "candidate_count"])


_EXAM_PROFILE = np.array([0.30, 0.25, 0.22, 0.12, 0.07, 0.04])
_CURR_PROFILE = {
    "arabic": np.array([0.14, 0.24, 0.24, 0.18, 0.12, 0.08]),
    "french": np.array([0.16, 0.24, 0.24, 0.18, 0.10, 0.08]),
    "math": np.array([0.10, 0.18, 0.30, 0.24, 0.10, 0.08]),
    "science": np.array([0.14, 0.22, 0.26, 0.20, 0.10, 0.08]),
}


def make_exam_items(seed: int = SYNTHETIC_SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed + 3)
    items, curr = [], []
    for sub in SUBJECTS:
        for y in YEARS[1:]:
            p = rng.dirichlet(_EXAM_PROFILE * 60)
            levels = rng.choice(len(BLOOM_LEVELS), size=40, p=p)
            for i, lv in enumerate(levels):
                success = float(np.clip(0.78 - 0.095 * lv + rng.normal(0, 0.05), 0.05, 0.95))
                items.append((y, sub, f"{sub[:3].upper()}-{y}-{i:02d}", BLOOM_LEVELS[lv][0], int(rng.integers(1, 4)), round(success, 3)))
        base = _CURR_PROFILE[sub]
        for lv, share in enumerate(base):
            curr.append((sub, BLOOM_LEVELS[lv][0], float(share)))
    return (
        pd.DataFrame(items, columns=["year", "subject", "item_id", "bloom_level", "points", "success_rate"]),
        pd.DataFrame(curr, columns=["subject", "bloom_level", "weight"]),
    )


def make_students(ctx: pd.DataFrame, n: int = 30_000, seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    """Synthetic *anonymous* pupil records. The drop-out outcome is generated by a KNOWN logistic
    rule (see DGP_COEFS): the model trained on it recovers our own assumptions, not empirical facts."""
    rng = np.random.default_rng(seed + 4)
    ctx_i = ctx.set_index("governorate")
    gk = rng.choice(KEYS, size=n, p=ctx["weight"].to_numpy())
    dep = ctx_i.loc[gk, "deprivation_index"].to_numpy()
    rural_p = ctx_i.loc[gk, "rural_share"].to_numpy()
    rural = (rng.random(n) < rural_p).astype(int)
    level = rng.choice(["primary", "secondary"], size=n, p=[0.5, 0.5])
    sex = rng.choice(["F", "M"], size=n)
    ses = rng.normal(0, 1, n) - 1.2 * (dep - 0.5)
    absence = np.clip(rng.beta(1.5, 12, n) + 0.04 * dep, 0, 0.6)
    repetition = rng.choice([0, 1, 2], size=n, p=[0.82, 0.14, 0.04])
    prior = np.clip(55 + 8 * ses + rng.normal(0, 12, n), 0, 100)
    class_size = np.clip(rng.normal(25, 5, n), 10, 45)
    distance = np.clip(rng.gamma(2.0, 1.1, n) * (1 + 0.8 * rural), 0.1, 30)
    c = DGP_COEFS
    logit = (
        c["intercept"] + c["secondary"] * (level == "secondary") + c["ses"] * ses + c["absence"] * absence
        + c["repetition"] * repetition + c["prior"] * (prior - 50) + c["distance"] * distance
        + c["class_size"] * (class_size - 25)
    )
    dropout = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame(
        {
            "governorate": gk, "level": level, "sex": sex, "rural": rural, "ses_index": ses.round(3),
            "absence_rate": absence.round(3), "repetitions": repetition, "prior_score": prior.round(1),
            "class_size": class_size.round(1), "distance_km": distance.round(2), "dropped_out": dropout,
        }
    )


# Declared data-generating rule: used only to create synthetic outcomes. Sex has NO effect by construction.
DGP_COEFS = {
    "intercept": -4.3, "secondary": 0.9, "ses": -0.45, "absence": 4.2, "repetition": 0.45,
    "prior": -0.022, "distance": 0.06, "class_size": 0.012,
}
