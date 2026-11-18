"""Dataset assembly, schema validation and replacement of synthetic data by official files."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from . import synthetic
from .config import CATALOG_PATH, GEO_PATH, GOVERNORATES, SUBJECTS, normalize_governorate
from .metrics import weighted_mean

# --------------------------------------------------------------------------------------
# Schemas for imported files
# --------------------------------------------------------------------------------------
SCHEMAS = {
    "institutions": {
        "required": ["governorate", "level", "pupils", "teachers", "classes"],
        "optional": ["institution_id", "equipment_index", "mean_score", "dropout_rate", "lat", "lon"],
        "numeric": ["pupils", "teachers", "classes", "equipment_index", "mean_score", "dropout_rate", "lat", "lon"],
        "level_values": ["primary", "secondary"],
        "help": "One row per institution. level = primary | secondary. equipment_index in [0,1]; dropout_rate in [0,1]; mean_score in [0,100].",
    },
    "results": {
        "required": ["governorate", "year", "level", "subject", "mean_score"],
        "optional": ["pass_rate", "candidate_count"],
        "numeric": ["year", "mean_score", "pass_rate", "candidate_count"],
        "level_values": ["primary", "secondary"],
        "help": "One row per governorate x year x level x subject. subject in arabic|french|math|science; optional candidate_count is the denominator for candidate-weighted success rates.",
    },
}


@lru_cache(maxsize=1)
def geojson() -> dict:
    with open(GEO_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def geo_centroids() -> dict[str, tuple[float, float]]:
    """(lat, lon) vertex-mean of the largest ring of each governorate (display purposes only)."""
    out = {}
    for feat in geojson()["features"]:
        name = feat["properties"]["shapeName"]
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        ring = max((p[0] for p in polys), key=len)
        arr = np.array(ring)
        out[name] = (float(arr[:, 1].mean()), float(arr[:, 0].mean()))
    return out


@dataclass
class DataBundle:
    context: pd.DataFrame
    institutions: pd.DataFrame
    results: pd.DataFrame
    exam_items: pd.DataFrame
    curriculum: pd.DataFrame
    students: pd.DataFrame
    provenance: dict[str, str] = field(default_factory=dict)  # dataset -> synthetic | imported_unverified | unavailable
    mode: str = "DEMONSTRATION"
    validation: dict[str, "ValidationReport"] = field(default_factory=dict)

    def governorates(self, level: str | None = None) -> pd.DataFrame:
        return governorate_table(self.institutions, self.context, level)


@lru_cache(maxsize=1)
def synthetic_bundle() -> DataBundle:
    ctx = synthetic.make_context()
    inst = synthetic.make_institutions(ctx, geo_centroids())
    results = synthetic.make_results(ctx)
    items, curr = synthetic.make_exam_items()
    students = synthetic.make_students(ctx)
    prov = {k: "synthetic" for k in ("institutions", "results", "exam_items", "curriculum", "students", "context")}
    return DataBundle(ctx, inst, results, items, curr, students, prov)


def build_bundle(overrides: dict[str, pd.DataFrame] | None = None, mode: str = "DEMONSTRATION",
                 validation: dict[str, "ValidationReport"] | None = None) -> DataBundle:
    """Build a strictly single-provenance bundle. DEMONSTRATION never consumes imports.

    REAL_DATA contains only explicitly imported/validated datasets; unavailable datasets
    are empty and marked unavailable, never silently filled from the synthetic generator.
    """
    mode = str(mode).upper()
    if mode not in {"DEMONSTRATION", "REAL_DATA"}:
        raise ValueError("mode must be DEMONSTRATION or REAL_DATA")
    names = ("context", "institutions", "results", "exam_items", "curriculum", "students")
    if mode == "DEMONSTRATION":
        base = synthetic_bundle()
        return DataBundle(**{k: getattr(base, k).copy(deep=True) for k in names},
                          provenance=dict(base.provenance), mode=mode)
    empty = {k: pd.DataFrame() for k in names}
    provenance = {k: "unavailable" for k in names}
    accepted = {}
    reports = {}
    for name, df in (overrides or {}).items():
        if name not in ("institutions", "results") or df is None or df.empty:
            continue
        report = validate_dataset(name, df)
        reports[name] = report
        if report.ok and report.clean is not None and not report.clean.empty:
            accepted[name] = report.clean.copy(deep=True)
            provenance[name] = "imported_unverified"
    empty.update(accepted)
    return DataBundle(**empty, provenance=provenance, mode=mode, validation=reports)


def export_frame(df: pd.DataFrame, mode: str, provenance: dict[str, str], datasets: tuple[str, ...]) -> bytes:
    """CSV export with explicit data mode, source provenance and a machine-readable warning."""
    out = df.copy()
    out.insert(0, "__tedt_mode", mode)
    out.insert(1, "__tedt_provenance", ";".join(f"{d}:{provenance.get(d, 'unavailable')}" for d in datasets))
    out.insert(2, "__tedt_warning", "SYNTHETIC_DEMONSTRATION_NOT_REAL" if mode == "DEMONSTRATION" else "REAL_DATA_SOURCE_NOT_CERTIFIED")
    return out.to_csv(index=False).encode("utf-8-sig")


def governorate_coverage(df: pd.DataFrame, column: str = "governorate") -> dict:
    observed = set(df[column].dropna()) if column in df.columns else set()
    missing = sorted(set(GOVERNORATES) - observed)
    return {"observed": len(observed & set(GOVERNORATES)), "expected": len(GOVERNORATES),
            "complete": not missing, "missing": missing}


# --------------------------------------------------------------------------------------
# Governorate-level aggregation
# --------------------------------------------------------------------------------------
def governorate_table(inst: pd.DataFrame, ctx: pd.DataFrame | None = None, level: str | None = None) -> pd.DataFrame:
    if inst.empty:
        raise ValueError("No institution data available for governorate aggregation.")
    df = inst if level in (None, "all") else inst[inst["level"] == level]
    if df.empty:
        raise ValueError(f"No institution observations for level={level!r}.")
    g = df.groupby("governorate", dropna=False)
    out = g.agg(institutions=("governorate", "size"), pupils=("pupils", "sum"), teachers=("teachers", "sum"), classes=("classes", "sum"))
    out["class_size"] = out["pupils"] / out["classes"].replace(0, np.nan)
    out["ptr"] = out["pupils"] / out["teachers"].replace(0, np.nan)
    for col in ("equipment_index", "mean_score", "dropout_rate"):
        if col in df.columns:
            out[col] = g.apply(lambda x, c=col: weighted_mean(x[c], x["pupils"]) if x[c].notna().any() else np.nan, include_groups=False)
        else:
            out[col] = np.nan
    out = out.reset_index().rename(columns={"mean_score": "quality", "dropout_rate": "dropout"})
    ctx = ctx if ctx is not None else pd.DataFrame()
    if not ctx.empty and "governorate" in ctx.columns:
        ctx_cols = [c for c in ("governorate", "deprivation_index", "rural_share") if c in ctx.columns]
        out = out.merge(ctx[ctx_cols].drop_duplicates("governorate"), on="governorate", how="left", validate="one_to_one")
        if "deprivation_index" not in out.columns:
            out["deprivation_index"] = np.nan
        if "rural_share" not in out.columns:
            out["rural_share"] = np.nan
    else:
        out["deprivation_index"] = _proxy_need(out)
        out["rural_share"] = np.nan
    if out["deprivation_index"].isna().any():
        proxy = _proxy_need(out)
        out["deprivation_index"] = out["deprivation_index"].fillna(proxy)
    source_values = out["deprivation_index"].notna()
    if not ctx.empty and "deprivation_index" in ctx.columns:
        source_map = ctx.drop_duplicates("governorate").set_index("governorate")["deprivation_index"]
        original_context = out["governorate"].map(source_map)
        out["deprivation_index_source"] = np.where(original_context.notna(), "source_context", np.where(source_values, "derived_proxy", "unavailable"))
    else:
        out["deprivation_index_source"] = np.where(source_values, "derived_proxy", "unavailable")
    out["name_fr"] = out["governorate"].map(lambda k: GOVERNORATES.get(k, (str(k), ""))[0])
    out["name_ar"] = out["governorate"].map(lambda k: GOVERNORATES.get(k, ("", str(k)))[1])
    return out


def _proxy_need(g: pd.DataFrame) -> pd.Series:
    """Derived need proxy from all three documented dimensions; never substitutes 0.5."""
    required = ("equipment_index", "quality", "dropout")
    if not all(c in g and g[c].notna().all() for c in required):
        return pd.Series(np.nan, index=g.index)
    low_equipment = (-g["equipment_index"]).rank(pct=True)
    low_quality = (-g["quality"]).rank(pct=True)
    high_dropout = g["dropout"].rank(pct=True)
    return pd.concat([low_equipment, low_quality, high_dropout], axis=1).mean(axis=1)


# --------------------------------------------------------------------------------------
# Validation of user-supplied files
# --------------------------------------------------------------------------------------
@dataclass
class ValidationReport:
    ok: bool
    errors: list[str]
    warnings: list[str]
    completeness: pd.DataFrame
    clean: pd.DataFrame | None
    quality_score: float  # 0-100
    rejected: pd.DataFrame = field(default_factory=pd.DataFrame)
    counts: dict[str, int] = field(default_factory=dict)


def validate_dataset(kind: str, df: pd.DataFrame) -> ValidationReport:
    if kind not in SCHEMAS:
        raise ValueError(f"Unknown dataset kind: {kind}")
    schema = SCHEMAS[kind]
    errors, warnings = [], []
    original = df.copy()
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if df.columns.duplicated().any():
        dup_cols = sorted(set(df.columns[df.columns.duplicated()].tolist()))
        errors.append(f"Duplicate column names: {', '.join(dup_cols)}")
        rejected = original.copy()
        rejected["rejection_reason"] = "duplicate_column_names"
        comp = pd.DataFrame(columns=["column", "completeness_pct", "status"])
        return ValidationReport(False, errors, warnings, comp, None, 0.0, rejected,
                                {"input": len(original), "accepted": 0, "rejected": len(original), "missing_columns": 0, "missing": 0, "invalid": 0, "not_applicable": 0})
    missing_cols = [c for c in schema["required"] if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {', '.join(missing_cols)}")
        comp = pd.DataFrame({"column": schema["required"] + schema["optional"],
                             "completeness_pct": [0.0 if c not in df else float(df[c].notna().mean()*100) for c in schema["required"] + schema["optional"]],
                             "status": ["missing_column" if c not in df else ("required" if c in schema["required"] else "optional") for c in schema["required"] + schema["optional"]]})
        rejected = original.copy()
        rejected["rejection_reason"] = "missing_required_columns"
        return ValidationReport(False, errors, warnings, comp, None, 0.0, rejected,
                                {"input": len(original), "accepted": 0, "rejected": len(original), "missing_columns": len(missing_cols), "missing": 0, "invalid": 0, "not_applicable": 0})
    keep = [c for c in schema["required"] + schema["optional"] if c in df.columns]
    df = df[keep]
    rejected_parts = []
    status_counts = {"missing": 0, "invalid": 0, "not_applicable": 0}
    na_tokens = {"", "null", "none", "nan", "<na>"}
    na_tokens_napp = {"n/a", "na", "not applicable", "not_applicable", "غير منطبق", "لا ينطبق"}
    for c in keep:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            text = df[c].astype("string").str.strip().str.lower()
            n_a = text.isin(na_tokens_napp)
            missing = text.isna() | text.isin(na_tokens)
            status_counts["not_applicable"] += int(n_a.sum())
            status_counts["missing"] += int(missing.sum())
            df.loc[n_a | missing, c] = np.nan
        else:
            status_counts["missing"] += int(df[c].isna().sum())
    # Keep the input-level completeness before invalid rows are rejected.
    df["governorate"] = df["governorate"].map(normalize_governorate)
    bad_gov = df["governorate"].isna()
    if bad_gov.any():
        status_counts["invalid"] += int(bad_gov.sum())
        warnings.append(f"{int(bad_gov.sum())} row(s) have an unknown governorate and will be rejected.")
    for c in schema["numeric"]:
        if c in df.columns:
            raw = df[c].copy()
            converted = pd.to_numeric(raw, errors="coerce")
            invalid = raw.notna() & converted.isna()
            status_counts["invalid"] += int(invalid.sum())
            if invalid.any():
                warnings.append(f"{int(invalid.sum())} invalid numeric value(s) in {c}.")
            df[c] = converted
    quality_frame = df.copy()
    def reject(mask, reason):
        nonlocal df
        mask = pd.Series(mask, index=df.index).fillna(False)
        if mask.any():
            bad = df.loc[mask].copy()
            bad["rejection_reason"] = reason
            rejected_parts.append(bad)
            df = df.loc[~mask].copy()
    reject(bad_gov, "unknown_governorate")
    for c in schema["required"]:
        reject(df[c].isna(), f"missing_or_invalid_required:{c}")
    if "level" in df.columns:
        df["level"] = df["level"].astype(str).str.strip().str.lower()
        bad_level = ~df["level"].isin(schema["level_values"])
        if bad_level.any():
            status_counts["invalid"] += int(bad_level.sum())
        reject(bad_level, "invalid_level")
    if kind == "institutions":
        for c in ("pupils", "teachers", "classes"):
            bad_nonpositive = df[c].notna() & (df[c] <= 0)
            if bad_nonpositive.any():
                status_counts["invalid"] += int(bad_nonpositive.sum())
                quality_frame.loc[bad_nonpositive.index[bad_nonpositive], c] = np.nan
            reject(bad_nonpositive, f"non_positive:{c}")
        for c, lo, hi in (("equipment_index", 0, 1), ("dropout_rate", 0, 1), ("mean_score", 0, 100), ("lat", -90, 90), ("lon", -180, 180)):
            if c in df.columns:
                bad = df[c].notna() & ((df[c] < lo) | (df[c] > hi))
                if bad.any():
                    status_counts["invalid"] += int(bad.sum())
                    warnings.append(f"{int(bad.sum())} out-of-range value(s) in {c}; outside permitted range; treated as invalid/missing.")
                    df.loc[bad, c] = np.nan
                    quality_frame.loc[bad.index[bad], c] = np.nan
        if "institution_id" in df.columns:
            ids = df["institution_id"].astype("string").str.strip()
            dup = ids.notna() & ids.ne("") & ids.duplicated(keep=False)
            reject(dup, "duplicate_institution_id")
            if ids.isna().any() or ids.eq("").any():
                warnings.append("Some institution_id values are absent; those entities cannot be reliably linked across datasets.")
        else:
            warnings.append("No authoritative institution_id supplied; exact duplicate rows are detected, but entity identity cannot be guaranteed.")
            reject(df.duplicated(keep=False), "duplicate_full_row")
    else:
        bad_year = df["year"].notna() & ((df["year"] % 1 != 0) | (df["year"] < 1900) | (df["year"] > 2100))
        if bad_year.any():
            status_counts["invalid"] += int(bad_year.sum())
            quality_frame.loc[bad_year.index[bad_year], "year"] = np.nan
            reject(bad_year, "invalid_school_year")
        bad_subject = df["subject"].notna() & ~df["subject"].isin(list(SUBJECTS))
        if bad_subject.any():
            status_counts["invalid"] += int(bad_subject.sum())
        reject(bad_subject, "invalid_subject")
        for c, lo, hi in (("mean_score", 0, 100), ("pass_rate", 0, 1)):
            if c in df.columns:
                bad = df[c].notna() & ((df[c] < lo) | (df[c] > hi))
                if bad.any():
                    status_counts["invalid"] += int(bad.sum())
                    quality_frame.loc[bad.index[bad], c] = np.nan
                    reject(bad, f"out_of_range:{c}")
        if "candidate_count" in df.columns:
            bad_count = df["candidate_count"].notna() & ((df["candidate_count"] <= 0) | (df["candidate_count"] % 1 != 0))
            if bad_count.any():
                status_counts["invalid"] += int(bad_count.sum())
                quality_frame.loc[bad_count.index[bad_count], "candidate_count"] = np.nan
                reject(bad_count, "invalid_candidate_count")
        reject(df.duplicated(subset=schema["required"], keep=False), "duplicate_result_key")
    if len(df) == 0:
        errors.append("No valid rows after cleaning.")
    supplied_optional = [c for c in schema["optional"] if c in keep]
    required_coverage = np.mean([float(quality_frame[c].notna().mean()) for c in schema["required"]]) if len(quality_frame) else 0.0
    optional_coverage = np.mean([float(quality_frame[c].notna().mean()) for c in supplied_optional]) if supplied_optional and len(quality_frame) else 1.0
    retention = (len(df) / len(original)) if len(original) else 0.0
    score = float(100 * (0.7 * required_coverage + 0.2 * optional_coverage + 0.1 * retention))
    comp_rows = []
    for c in schema["required"] + schema["optional"]:
        if c not in keep:
            comp_rows.append((c, 0.0, "missing_column"))
        else:
            pct = float(quality_frame[c].notna().mean() * 100) if len(quality_frame) else 0.0
            comp_rows.append((c, round(pct, 1), "required" if c in schema["required"] else "optional"))
    comp = pd.DataFrame(comp_rows, columns=["column", "completeness_pct", "status"])
    rejected = pd.concat(rejected_parts, ignore_index=True) if rejected_parts else pd.DataFrame(columns=keep + ["rejection_reason"])
    counts = {"input": len(original), "accepted": len(df), "rejected": len(rejected), "missing_columns": len(missing_cols), **status_counts}
    coverage = governorate_coverage(df)
    if kind == "institutions" and not coverage["complete"]:
        warnings.append(f"Institution file covers {coverage['observed']}/{coverage['expected']} governorates; national modules will be blocked.")
    if kind == "results" and not coverage["complete"]:
        warnings.append(f"Results file covers {coverage['observed']}/{coverage['expected']} governorates; national interpretation is not supported.")
    return ValidationReport(not errors, errors, warnings, comp, df.reset_index(drop=True) if not errors else None,
                            round(score, 1), rejected, counts)


def read_uploaded(file) -> pd.DataFrame:
    name = getattr(file, "name", "").lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    return pd.read_csv(file, sep=None, engine="python")


# --------------------------------------------------------------------------------------
# Source catalog (data feasibility matrix)
# --------------------------------------------------------------------------------------
STATUS_WEIGHT = {1: 1.0, 2: 0.6, 3: 0.25, 4: 0.0}


def load_catalog() -> pd.DataFrame:
    return pd.read_csv(CATALOG_PATH)


def readiness_index(catalog: pd.DataFrame) -> float:
    """Documentary readiness index (0-100): mean of status weights over catalogued sources.
    It measures what is documented, not data quality. Weights: 1->1.0, 2->0.6, 3->0.25, 4->0."""
    return float(catalog["status"].map(STATUS_WEIGHT).mean() * 100)
