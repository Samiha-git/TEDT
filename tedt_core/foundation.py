"""TEDT Education Data Foundation: immutable staging, provenance and metadata registry.

Lot 1 deliberately accepts only public or institutional non-sensitive aggregate files.
It does not certify source authenticity or authorize reuse; these remain explicit metadata.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tedt_core.config import DATA_DIR

FOUNDATION_DB = DATA_DIR / "tedt_foundation.sqlite"
STAGING_DIR = DATA_DIR / "staging"
SOURCE_REGISTER = DATA_DIR / "foundation" / "source_register.csv"
INDICATOR_DICTIONARY = DATA_DIR / "foundation" / "indicator_dictionary.csv"

ALLOWED_CLASSIFICATIONS = {"PUBLIC", "INSTITUTIONAL_NON_SENSITIVE"}
BATCH_STATES = {"RECEIVED", "PROFILED", "VALIDATED", "MAPPED", "APPROVED", "LOADED", "REJECTED", "QUARANTINED", "SUPERSEDED"}
REQUIRED_METADATA = {
    "source_id", "dataset_code", "source_owner", "source_title", "source_reference",
    "reference_period_start", "reference_period_end", "geographic_level", "granularity",
    "declared_license_or_authorization", "security_classification", "language", "schema_version",
}

# Only explicit personal identifiers/attributes are blocked. Generic "name" is not blocked
# because public establishment registers legitimately contain institution names.
SENSITIVE_COLUMN_PATTERNS = (
    r"(^|_)(student|pupil|learner|teacher|parent|guardian)_?(name|id|number|phone|email|address)?($|_)",
    r"(^|_)(cin|national_id|passport|phone|mobile|email|birth_date|date_of_birth|home_address)($|_)",
    r"(^|_)(matricule_personnel|student_number|teacher_number|dossier_individuel)($|_)",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db_path: Path | str = FOUNDATION_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(db_path: Path | str = FOUNDATION_DB) -> None:
    """Create the Lot 1 metadata, master-register and warehouse structures idempotently."""
    with _connect(db_path) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS source (
            source_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, owner TEXT NOT NULL,
            url TEXT, access_status INTEGER, access_conditions TEXT, reuse_conditions TEXT,
            verified_at TEXT, verification_note TEXT
        );
        CREATE TABLE IF NOT EXISTS dataset (
            dataset_code TEXT PRIMARY KEY, dataset_name TEXT NOT NULL, family TEXT,
            expected_grain TEXT, security_classification TEXT NOT NULL DEFAULT 'PUBLIC',
            schema_version TEXT NOT NULL DEFAULT '1.0'
        );
        CREATE TABLE IF NOT EXISTS ingestion_batch (
            batch_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, dataset_code TEXT NOT NULL,
            source_owner TEXT NOT NULL, source_title TEXT NOT NULL, source_reference TEXT NOT NULL,
            received_at TEXT NOT NULL, received_by TEXT NOT NULL,
            reference_period_start TEXT NOT NULL, reference_period_end TEXT NOT NULL,
            geographic_level TEXT NOT NULL, granularity TEXT NOT NULL,
            declared_license_or_authorization TEXT NOT NULL,
            security_classification TEXT NOT NULL, language TEXT NOT NULL,
            source_filename TEXT NOT NULL, stored_filename TEXT NOT NULL,
            sha256 TEXT NOT NULL, file_size INTEGER NOT NULL, file_format TEXT NOT NULL,
            schema_version TEXT NOT NULL, state TEXT NOT NULL, row_count INTEGER,
            column_count INTEGER, profile_json TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(dataset_code) REFERENCES dataset(dataset_code)
        );
        CREATE TABLE IF NOT EXISTS validation_run (
            validation_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, rules_version TEXT NOT NULL,
            status TEXT NOT NULL, quality_json TEXT NOT NULL, run_at TEXT NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS validation_issue (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT, validation_id TEXT NOT NULL,
            severity TEXT NOT NULL, issue_code TEXT NOT NULL, column_name TEXT,
            row_number INTEGER, message TEXT NOT NULL,
            FOREIGN KEY(validation_id) REFERENCES validation_run(validation_id)
        );
        CREATE TABLE IF NOT EXISTS transformation_run (
            transformation_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, mapping_version TEXT NOT NULL,
            transformation_spec TEXT NOT NULL, actor TEXT NOT NULL, executed_at TEXT NOT NULL,
            status TEXT NOT NULL, output_sha256 TEXT,
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS institution (
            tedt_institution_id TEXT PRIMARY KEY, official_id TEXT, official_id_issuer TEXT,
            id_status TEXT NOT NULL CHECK(id_status IN ('official_verified','provisional_internal','unresolved')),
            created_at TEXT NOT NULL, created_by TEXT NOT NULL,
            UNIQUE(official_id_issuer, official_id)
        );
        CREATE TABLE IF NOT EXISTS institution_version (
            institution_version_id TEXT PRIMARY KEY, tedt_institution_id TEXT NOT NULL,
            name_fr TEXT, name_ar TEXT, institution_type TEXT, education_level TEXT,
            status TEXT, authority TEXT, governorate TEXT, delegation TEXT, geographic_sector TEXT,
            latitude REAL, longitude REAL, valid_from TEXT, valid_to TEXT,
            recorded_at TEXT NOT NULL, superseded_at TEXT, source_id TEXT, batch_id TEXT,
            change_reason TEXT,
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS institution_alias (
            alias_id TEXT PRIMARY KEY, tedt_institution_id TEXT NOT NULL, alias TEXT NOT NULL,
            language TEXT, valid_from TEXT, valid_to TEXT, source_id TEXT,
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id)
        );
        CREATE TABLE IF NOT EXISTS institution_relation (
            relation_id TEXT PRIMARY KEY, from_institution_id TEXT NOT NULL,
            to_institution_id TEXT NOT NULL, relation_type TEXT NOT NULL,
            effective_date TEXT, source_id TEXT, justification TEXT,
            FOREIGN KEY(from_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(to_institution_id) REFERENCES institution(tedt_institution_id)
        );
        CREATE TABLE IF NOT EXISTS indicator_dictionary (
            indicator_code TEXT NOT NULL, version TEXT NOT NULL, label_fr TEXT NOT NULL,
            label_ar TEXT, indicator_type TEXT NOT NULL, definition TEXT NOT NULL,
            analytical_purpose TEXT, formula TEXT, numerator TEXT, denominator TEXT,
            unit TEXT, grain TEXT, disaggregation TEXT, periodicity TEXT,
            reference_period TEXT, source_owner TEXT, reliability_status TEXT,
            methodological_limits TEXT, missing_value_rule TEXT, status TEXT NOT NULL,
            PRIMARY KEY(indicator_code, version)
        );
        CREATE TABLE IF NOT EXISTS dim_geography (
            geography_id TEXT PRIMARY KEY, geography_level TEXT NOT NULL,
            canonical_code TEXT, name_fr TEXT NOT NULL, name_ar TEXT,
            parent_geography_id TEXT, nomenclature_code TEXT, nomenclature_version TEXT,
            valid_from TEXT, valid_to TEXT,
            FOREIGN KEY(parent_geography_id) REFERENCES dim_geography(geography_id)
        );
        CREATE TABLE IF NOT EXISTS dim_period (
            period_id TEXT PRIMARY KEY, period_type TEXT NOT NULL, period_label TEXT NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, calendar_system TEXT NOT NULL DEFAULT 'gregorian'
        );
        CREATE TABLE IF NOT EXISTS dim_education_level (
            education_level_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT,
            level_order INTEGER, framework_version TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_sex (
            sex_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT, source_code TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_milieu (
            milieu_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT, source_code TEXT
        );
        CREATE TABLE IF NOT EXISTS fact_enrolment (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, sex_code TEXT, enrolled_count REAL, eligible_population REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(sex_code) REFERENCES dim_sex(sex_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_staff (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, discipline_code TEXT, staff_count REAL, vacancy_count REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_infrastructure (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            asset_type TEXT NOT NULL, asset_count REAL, operational_count REAL, condition_code TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_learning_outcome (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, subject_code TEXT, assessment_code TEXT,
            candidate_count REAL, successful_count REAL, mean_score REAL, published_rate REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_territorial_indicator (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT NOT NULL,
            indicator_code TEXT NOT NULL, indicator_version TEXT NOT NULL, dimension_json TEXT NOT NULL,
            value REAL, numerator REAL, denominator REAL, unit TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(indicator_code,indicator_version) REFERENCES indicator_dictionary(indicator_code,version),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_expenditure (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT,
            programme_code TEXT, education_level_code TEXT, expenditure_nature TEXT,
            budget_amount REAL, executed_amount REAL, currency_code TEXT NOT NULL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE TABLE IF NOT EXISTS fact_observation (
            observation_id TEXT PRIMARY KEY, indicator_code TEXT NOT NULL,
            indicator_version TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
            geography_id TEXT, tedt_institution_id TEXT, dimension_json TEXT NOT NULL,
            value REAL, numerator REAL, denominator REAL, unit TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            loaded_at TEXT NOT NULL,
            FOREIGN KEY(indicator_code, indicator_version) REFERENCES indicator_dictionary(indicator_code, version),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );
        CREATE INDEX IF NOT EXISTS idx_batch_source ON ingestion_batch(source_id, dataset_code);
        CREATE INDEX IF NOT EXISTS idx_fact_indicator_period ON fact_observation(indicator_code, period_start, period_end);
        CREATE INDEX IF NOT EXISTS idx_institution_official ON institution(official_id, official_id_issuer);
        """)


def register_source(source: dict[str, Any], db_path: Path | str = FOUNDATION_DB) -> None:
    initialize(db_path)
    with _connect(db_path) as con:
        con.execute("""INSERT INTO source(source_id,source_name,owner,url,access_status,access_conditions,reuse_conditions,verified_at,verification_note)
        VALUES(:source_id,:source_name,:owner,:url,:access_status,:access_conditions,:reuse_conditions,:verified_at,:verification_note)
        ON CONFLICT(source_id) DO UPDATE SET source_name=excluded.source_name, owner=excluded.owner,
        url=excluded.url, access_status=excluded.access_status, access_conditions=excluded.access_conditions,
        reuse_conditions=excluded.reuse_conditions, verified_at=excluded.verified_at,
        verification_note=excluded.verification_note""", source)


def register_dataset(dataset: dict[str, Any], db_path: Path | str = FOUNDATION_DB) -> None:
    initialize(db_path)
    with _connect(db_path) as con:
        con.execute("""INSERT INTO dataset(dataset_code,dataset_name,family,expected_grain,security_classification,schema_version)
        VALUES(:dataset_code,:dataset_name,:family,:expected_grain,:security_classification,:schema_version)
        ON CONFLICT(dataset_code) DO UPDATE SET dataset_name=excluded.dataset_name, family=excluded.family,
        expected_grain=excluded.expected_grain, security_classification=excluded.security_classification,
        schema_version=excluded.schema_version""", dataset)


def seed_reference_files(db_path: Path | str = FOUNDATION_DB) -> dict[str, int]:
    """Seed only the reviewed local CSV registries; no external source is inferred."""
    initialize(db_path)
    sources = pd.read_csv(SOURCE_REGISTER).fillna("") if SOURCE_REGISTER.exists() else pd.DataFrame()
    indicators = pd.read_csv(INDICATOR_DICTIONARY).fillna("") if INDICATOR_DICTIONARY.exists() else pd.DataFrame()
    for row in sources.to_dict("records"):
        register_source({
            "source_id": row["source_id"], "source_name": row["source_name"], "owner": row["owner"],
            "url": row.get("url") or None, "access_status": int(row["status_code"]) if str(row.get("status_code", "")).isdigit() else None,
            "access_conditions": row.get("access_conditions", ""), "reuse_conditions": row.get("access_conditions", ""),
            "verified_at": None, "verification_note": row.get("verification_note", ""),
        }, db_path)
    for row in indicators.to_dict("records"):
        cols = ["indicator_code", "version", "label_fr", "label_ar", "indicator_type", "definition", "analytical_purpose", "formula", "numerator", "denominator", "unit", "grain", "disaggregation", "periodicity", "reference_period", "source_owner", "reliability_status", "methodological_limits", "missing_value_rule", "status"]
        values = {k: row.get(k, "") for k in cols}
        with _connect(db_path) as con:
            con.execute(f"INSERT OR REPLACE INTO indicator_dictionary({','.join(cols)}) VALUES({','.join(':'+c for c in cols)})", values)
    return {"sources": len(sources), "indicators": len(indicators)}


def read_tabular_file(filename: str, content: bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"CSV encoding could not be detected: {last_error}")
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, engine="openpyxl")
    if suffix == ".xls":
        raise ValueError("Legacy .xls is not enabled in this build; save the workbook as .xlsx or CSV.")
    raise ValueError("Unsupported format. Accepted formats: CSV and XLSX.")


def detect_personal_columns(columns: list[str]) -> list[str]:
    found = []
    for col in columns:
        normalized = re.sub(r"[^a-z0-9_]+", "_", str(col).strip().lower())
        if any(re.search(pattern, normalized) for pattern in SENSITIVE_COLUMN_PATTERNS):
            found.append(str(col))
    return found


def profile_frame(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"rows": 0, "columns": len(df.columns), "variables": []}
    variables = []
    for col in df.columns:
        s = df[col]
        variables.append({
            "name": str(col), "dtype": str(s.dtype), "non_missing": int(s.notna().sum()),
            "missing": int(s.isna().sum()), "distinct": int(s.nunique(dropna=True)),
        })
    return {"rows": int(len(df)), "columns": int(len(df.columns)), "variables": variables}


def ingest_file(
    filename: str, content: bytes, metadata: dict[str, Any],
    *, base_dir: Path | str = DATA_DIR, db_path: Path | str = FOUNDATION_DB,
    received_by: str = "unassigned", sheet_name: str | int = 0,
) -> dict[str, Any]:
    """Preserve original bytes and register a RECEIVED/PROFILED batch.

    This step does not validate a domain schema, harmonize or load warehouse facts.
    It refuses personal/sensitive classifications and obvious individual identifiers.
    """
    missing = sorted(REQUIRED_METADATA - set(metadata))
    if missing:
        raise ValueError("Missing ingestion metadata: " + ", ".join(missing))
    classification = str(metadata["security_classification"]).upper()
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError("Lot 1 accepts PUBLIC or INSTITUTIONAL_NON_SENSITIVE data only.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    df = read_tabular_file(filename, content, sheet_name=sheet_name)
    if df.empty:
        raise ValueError("The uploaded file contains no observations.")
    personal = detect_personal_columns(list(df.columns))
    if personal:
        raise ValueError("Potential personal/individual fields detected; file quarantined: " + ", ".join(personal))
    batch_id = str(uuid.uuid4())
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(filename).suffix.lower()
    batch_dir = Path(base_dir) / "staging" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    stored_name = "original" + suffix
    raw_path = batch_dir / stored_name
    raw_path.write_bytes(content)
    try:
        raw_path.chmod(0o440)
    except OSError:
        pass
    manifest = {
        **metadata, "batch_id": batch_id, "received_at": _now(), "received_by": received_by,
        "source_filename": Path(filename).name, "stored_filename": stored_name,
        "sha256": digest, "file_size": len(content), "file_format": suffix.lstrip("."),
        "profile": profile_frame(df), "state": "PROFILED",
    }
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    initialize(db_path)
    with _connect(db_path) as con:
        # Source and dataset must be registered explicitly; no implicit source creation.
        if not con.execute("SELECT 1 FROM source WHERE source_id=?", (metadata["source_id"],)).fetchone():
            shutil.rmtree(batch_dir, ignore_errors=True)
            raise ValueError(f"Unknown source_id: {metadata['source_id']}. Register the source before import.")
        if not con.execute("SELECT 1 FROM dataset WHERE dataset_code=?", (metadata["dataset_code"],)).fetchone():
            con.execute("INSERT INTO dataset(dataset_code,dataset_name,family,expected_grain,security_classification,schema_version) VALUES(?,?,?,?,?,?)",
                        (metadata["dataset_code"], metadata["source_title"], metadata.get("family"), metadata["granularity"], classification, metadata["schema_version"]))
        con.execute("""INSERT INTO ingestion_batch(
            batch_id,source_id,dataset_code,source_owner,source_title,source_reference,received_at,received_by,
            reference_period_start,reference_period_end,geographic_level,granularity,declared_license_or_authorization,
            security_classification,language,source_filename,stored_filename,sha256,file_size,file_format,
            schema_version,state,row_count,column_count,profile_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (batch_id, metadata["source_id"], metadata["dataset_code"], metadata["source_owner"], metadata["source_title"],
             metadata["source_reference"], manifest["received_at"], received_by, metadata["reference_period_start"],
             metadata["reference_period_end"], metadata["geographic_level"], metadata["granularity"],
             metadata["declared_license_or_authorization"], classification, metadata["language"], Path(filename).name,
             stored_name, digest, len(content), suffix.lstrip("."), metadata["schema_version"], "PROFILED",
             len(df), len(df.columns), json.dumps(manifest["profile"], ensure_ascii=False), manifest["received_at"]))
    return {"batch_id": batch_id, "sha256": digest, "raw_path": str(raw_path), "manifest_path": str(batch_dir / "manifest.json"),
            "state": "PROFILED", "profile": manifest["profile"], "preview": df.head(10)}


def list_batches(db_path: Path | str = FOUNDATION_DB) -> pd.DataFrame:
    initialize(db_path)
    with _connect(db_path) as con:
        return pd.read_sql_query("""SELECT batch_id,source_id,dataset_code,source_title,source_owner,
            reference_period_start,reference_period_end,geographic_level,security_classification,
            sha256,file_format,state,row_count,column_count,received_at FROM ingestion_batch ORDER BY received_at DESC""", con)


def quality_summary(db_path: Path | str = FOUNDATION_DB) -> dict[str, Any]:
    """Operational quality metrics; unknown dimensions remain null, not zero."""
    batches = list_batches(db_path)
    if batches.empty:
        return {"batches": batches, "total_batches": 0, "by_state": {}, "by_source": pd.DataFrame(),
                "issues": pd.DataFrame(), "missing_periods": pd.DataFrame()}
    with _connect(db_path) as con:
        by_source = pd.read_sql_query("""SELECT source_id, dataset_code, COUNT(*) batches,
            SUM(CASE WHEN state IN ('VALIDATED','MAPPED','APPROVED','LOADED') THEN 1 ELSE 0 END) validated_batches,
            SUM(row_count) rows_received, MAX(received_at) last_received
            FROM ingestion_batch GROUP BY source_id,dataset_code ORDER BY source_id,dataset_code""", con)
        issues = pd.read_sql_query("""SELECT vr.batch_id,vi.severity,vi.issue_code,vi.column_name,vi.row_number,vi.message
            FROM validation_issue vi JOIN validation_run vr USING(validation_id)
            ORDER BY vr.run_at DESC""", con)
        runs = con.execute("SELECT batch_id,quality_json FROM validation_run ORDER BY run_at DESC").fetchall()
    variable_rows = []
    seen_batches = set()
    for run in runs:
        if run["batch_id"] in seen_batches:
            continue
        seen_batches.add(run["batch_id"])
        payload = json.loads(run["quality_json"])
        for variable in payload.get("variable_profile", []):
            variable_rows.append({"batch_id": run["batch_id"], "variable": variable["name"],
                                  "missing": variable["missing"], "non_missing": variable["non_missing"],
                                  "completeness_pct": round(100 * variable["non_missing"] / max(1, variable["missing"] + variable["non_missing"]), 2)})
    return {"batches": batches, "total_batches": len(batches), "by_state": batches["state"].value_counts().to_dict(),
            "by_source": by_source, "issues": issues, "variable_quality": pd.DataFrame(variable_rows),
            "missing_periods": pd.DataFrame(),
            "missing_periods_note": "Non calculable tant que la périodicité attendue n'est pas déclarée pour le jeu."}


def create_provisional_institution(name_fr: str, *, name_ar: str | None = None,
                                   created_by: str = "unassigned", db_path: Path | str = FOUNDATION_DB) -> str:
    """Create an explicitly provisional internal institution key; never an official identifier."""
    initialize(db_path)
    ident = str(uuid.uuid4())
    now = _now()
    with _connect(db_path) as con:
        con.execute("INSERT INTO institution(tedt_institution_id,official_id,official_id_issuer,id_status,created_at,created_by) VALUES(?,?,?,?,?,?)",
                    (ident, None, None, "provisional_internal", now, created_by))
        con.execute("""INSERT INTO institution_version(institution_version_id,tedt_institution_id,name_fr,name_ar,recorded_at,change_reason)
                    VALUES(?,?,?,?,?,?)""", (str(uuid.uuid4()), ident, name_fr, name_ar, now, "Création interne provisoire"))
    return ident


def register_official_institution(official_id: str, issuer: str, name_fr: str, *,
                                  source_id: str, created_by: str, db_path: Path | str = FOUNDATION_DB) -> str:
    """Register an issuer-provided identifier; uniqueness is enforced by issuer + official ID."""
    initialize(db_path)
    ident = str(uuid.uuid4())
    now = _now()
    with _connect(db_path) as con:
        if not con.execute("SELECT 1 FROM source WHERE source_id=?", (source_id,)).fetchone():
            raise ValueError("The source must be registered before adding an official identifier.")
        con.execute("INSERT INTO institution(tedt_institution_id,official_id,official_id_issuer,id_status,created_at,created_by) VALUES(?,?,?,?,?,?)",
                    (ident, str(official_id), issuer, "official_verified", now, created_by))
        con.execute("""INSERT INTO institution_version(institution_version_id,tedt_institution_id,name_fr,recorded_at,source_id,change_reason)
                    VALUES(?,?,?,?,?,?)""", (str(uuid.uuid4()), ident, name_fr, now, source_id, "Identifiant fourni par l'émetteur déclaré"))
    return ident


def load_batch_frame(batch_id: str, *, base_dir: Path | str = DATA_DIR, db_path: Path | str = FOUNDATION_DB) -> pd.DataFrame:
    initialize(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT source_filename,stored_filename,sha256 FROM ingestion_batch WHERE batch_id=?", (batch_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown batch_id: {batch_id}")
    raw_path = Path(base_dir) / "staging" / batch_id / row["stored_filename"]
    if not raw_path.exists():
        raise FileNotFoundError(f"Staged original is missing for batch {batch_id}")
    raw_bytes = raw_path.read_bytes()
    actual_digest = hashlib.sha256(raw_bytes).hexdigest()
    if actual_digest != row["sha256"]:
        raise ValueError(f"Staging integrity failure for batch {batch_id}: SHA-256 mismatch.")
    return read_tabular_file(row["source_filename"], raw_bytes)


def validate_batch(batch_id: str, *, required_columns: list[str] | None = None,
                   unique_columns: list[str] | None = None,
                   rules_version: str = "foundation-generic-1.0",
                   base_dir: Path | str = DATA_DIR, db_path: Path | str = FOUNDATION_DB) -> dict[str, Any]:
    """Run generic, non-destructive structural checks and retain every issue.

    Domain-specific indicator validation and harmonization remain separate steps.
    """
    frame = load_batch_frame(batch_id, base_dir=base_dir, db_path=db_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized = [str(c).strip() for c in frame.columns]
    if len(set(normalized)) != len(normalized):
        errors.append({"severity": "ERROR", "issue_code": "DUPLICATE_COLUMNS", "column_name": None,
                       "row_number": None, "message": "Duplicate column names after trimming whitespace."})
    missing_cols = sorted(set(required_columns or []) - set(normalized))
    for col in missing_cols:
        errors.append({"severity": "ERROR", "issue_code": "REQUIRED_COLUMN_MISSING", "column_name": col,
                       "row_number": None, "message": f"Required column '{col}' is absent."})
    for col in (unique_columns or []):
        if col not in frame.columns:
            warnings.append({"severity": "WARNING", "issue_code": "UNIQUE_COLUMN_NOT_FOUND", "column_name": col,
                             "row_number": None, "message": f"Uniqueness check skipped; column '{col}' is absent."})
        else:
            dup_mask = frame[col].notna() & frame[col].duplicated(keep=False)
            for idx in frame.index[dup_mask][:1000]:
                errors.append({"severity": "ERROR", "issue_code": "DUPLICATE_KEY", "column_name": col,
                               "row_number": int(frame.index.get_loc(idx)) + 2, "message": f"Duplicate value in key column '{col}'."})
    empty_cols = [str(c) for c in frame.columns if frame[c].isna().all()]
    for col in empty_cols:
        warnings.append({"severity": "WARNING", "issue_code": "ALL_VALUES_MISSING", "column_name": col,
                         "row_number": None, "message": f"All values are missing in '{col}'."})
    profile = profile_frame(frame)
    total_cells = max(1, frame.shape[0] * frame.shape[1])
    missing_cells = int(frame.isna().sum().sum())
    duplicate_rows = int(frame.duplicated().sum())
    quality = {
        "availability": 1.0, "completeness": round(1 - missing_cells / total_cells, 6),
        "uniqueness": round(1 - duplicate_rows / max(1, len(frame)), 6),
        "traceability": 1.0, "interoperability": None, "accuracy": None,
        "consistency": None, "timeliness": None,
        "missing_cells": missing_cells, "total_cells": total_cells,
        "duplicate_rows": duplicate_rows, "row_count": len(frame), "column_count": len(frame.columns),
        "variable_profile": profile["variables"],
        "note": "Unknown quality dimensions are null; no composite certification score is calculated.",
    }
    validation_id = str(uuid.uuid4())
    status = "REJECTED" if errors else "VALIDATED"
    with _connect(db_path) as con:
        con.execute("INSERT INTO validation_run(validation_id,batch_id,rules_version,status,quality_json,run_at) VALUES(?,?,?,?,?,?)",
                    (validation_id, batch_id, rules_version, status, json.dumps(quality, ensure_ascii=False), _now()))
        for issue in errors + warnings:
            con.execute("""INSERT INTO validation_issue(validation_id,severity,issue_code,column_name,row_number,message)
                        VALUES(?,?,?,?,?,?)""", (validation_id, issue["severity"], issue["issue_code"], issue["column_name"], issue["row_number"], issue["message"]))
        con.execute("UPDATE ingestion_batch SET state=?,profile_json=? WHERE batch_id=?",
                    (status, json.dumps(profile, ensure_ascii=False), batch_id))
    return {"validation_id": validation_id, "status": status, "quality": quality,
            "errors": errors, "warnings": warnings}


def get_batch_detail(batch_id: str, db_path: Path | str = FOUNDATION_DB) -> dict[str, Any]:
    initialize(db_path)
    with _connect(db_path) as con:
        batch = con.execute("SELECT * FROM ingestion_batch WHERE batch_id=?", (batch_id,)).fetchone()
        if batch is None:
            raise KeyError(batch_id)
        validations = con.execute("SELECT * FROM validation_run WHERE batch_id=? ORDER BY run_at DESC", (batch_id,)).fetchall()
    return {"batch": dict(batch), "validations": [dict(v) for v in validations]}
