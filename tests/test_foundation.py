import hashlib
import json

import pandas as pd
import pytest

from tedt_core import foundation


def _metadata(source_id="SRC-TEST", dataset_code="DS-TEST"):
    return {
        "source_id": source_id,
        "dataset_code": dataset_code,
        "source_owner": "Test institution",
        "source_title": "Aggregate education test dataset",
        "source_reference": "https://example.invalid/source-record",
        "reference_period_start": "2024",
        "reference_period_end": "2024",
        "geographic_level": "governorate",
        "granularity": "governorate x year",
        "declared_license_or_authorization": "Public publication; reuse conditions to be checked",
        "security_classification": "PUBLIC",
        "language": "fr",
        "schema_version": "1.0",
    }


def _setup(tmp_path):
    db = tmp_path / "foundation.sqlite"
    foundation.initialize(db)
    foundation.register_source({
        "source_id": "SRC-TEST", "source_name": "Test source", "owner": "Test institution",
        "url": "https://example.invalid", "access_status": 1,
        "access_conditions": "public", "reuse_conditions": "to verify",
        "verified_at": None, "verification_note": "test only",
    }, db)
    return db


def test_foundation_schema_is_created_idempotently(tmp_path):
    db = tmp_path / "foundation.sqlite"
    foundation.initialize(db)
    foundation.initialize(db)
    with foundation._connect(db) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"source", "ingestion_batch", "institution", "institution_version", "indicator_dictionary", "fact_observation"} <= tables


def test_import_preserves_original_bytes_and_metadata(tmp_path):
    db = _setup(tmp_path)
    raw = b"governorate,rate\nTunis,97.2\nSfax,96.8\n"
    result = foundation.ingest_file("pilot.csv", raw, _metadata(), base_dir=tmp_path, db_path=db, received_by="analyst-1")
    assert result["state"] == "PROFILED"
    assert open(result["raw_path"], "rb").read() == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    manifest = json.loads(open(result["manifest_path"], encoding="utf-8").read())
    assert manifest["source_id"] == "SRC-TEST"
    assert manifest["received_by"] == "analyst-1"
    batches = foundation.list_batches(db)
    assert len(batches) == 1 and batches.iloc[0]["state"] == "PROFILED"


def test_import_refuses_personal_classification(tmp_path):
    db = _setup(tmp_path)
    meta = _metadata()
    meta["security_classification"] = "PERSONAL_SENSITIVE"
    with pytest.raises(ValueError, match="accepts PUBLIC"):
        foundation.ingest_file("data.csv", b"governorate,rate\nTunis,97\n", meta, base_dir=tmp_path, db_path=db)


def test_import_refuses_obvious_individual_identifiers(tmp_path):
    db = _setup(tmp_path)
    raw = b"governorate,student_name\nTunis,Example\n"
    with pytest.raises(ValueError, match="Potential personal"):
        foundation.ingest_file("data.csv", raw, _metadata(), base_dir=tmp_path, db_path=db)


def test_import_requires_registered_source(tmp_path):
    db = tmp_path / "foundation.sqlite"
    foundation.initialize(db)
    with pytest.raises(ValueError, match="Unknown source_id"):
        foundation.ingest_file("data.csv", b"governorate,rate\nTunis,97\n", _metadata(), base_dir=tmp_path, db_path=db)


def test_generic_validation_records_duplicates_and_missingness(tmp_path):
    db = _setup(tmp_path)
    raw = b"governorate,rate\nTunis,97.2\nTunis,97.2\nSfax,\n"
    result = foundation.ingest_file("pilot.csv", raw, _metadata(), base_dir=tmp_path, db_path=db)
    validation = foundation.validate_batch(result["batch_id"], unique_columns=["governorate"], base_dir=tmp_path, db_path=db)
    assert validation["status"] == "REJECTED"
    assert validation["quality"]["missing_cells"] == 1
    assert validation["quality"]["duplicate_rows"] == 1
    assert validation["errors"]
    detail = foundation.get_batch_detail(result["batch_id"], db)
    assert detail["batch"]["state"] == "REJECTED"
    assert detail["validations"]


def test_generic_validation_passes_without_claiming_unknown_quality(tmp_path):
    db = _setup(tmp_path)
    raw = b"governorate,rate\nTunis,97.2\nSfax,96.8\n"
    result = foundation.ingest_file("pilot.csv", raw, _metadata(), base_dir=tmp_path, db_path=db)
    validation = foundation.validate_batch(result["batch_id"], required_columns=["governorate", "rate"], base_dir=tmp_path, db_path=db)
    assert validation["status"] == "VALIDATED"
    assert validation["quality"]["accuracy"] is None
    assert validation["quality"]["timeliness"] is None


def test_missing_required_column_rejects_batch(tmp_path):
    db = _setup(tmp_path)
    result = foundation.ingest_file("pilot.csv", b"governorate\nTunis\n", _metadata(), base_dir=tmp_path, db_path=db)
    validation = foundation.validate_batch(result["batch_id"], required_columns=["governorate", "rate"], base_dir=tmp_path, db_path=db)
    assert validation["status"] == "REJECTED"
    assert any(i["issue_code"] == "REQUIRED_COLUMN_MISSING" for i in validation["errors"])


def test_provisional_institution_identifier_is_explicitly_non_official(tmp_path):
    db = _setup(tmp_path)
    ident = foundation.create_provisional_institution("École test", created_by="analyst", db_path=db)
    with foundation._connect(db) as con:
        row = con.execute("SELECT official_id,id_status FROM institution WHERE tedt_institution_id=?", (ident,)).fetchone()
    assert row["official_id"] is None
    assert row["id_status"] == "provisional_internal"


def test_official_identifier_requires_registered_source_and_is_unique(tmp_path):
    db = _setup(tmp_path)
    ident = foundation.register_official_institution("MEN-001", "Ministère de l'Éducation", "École test", source_id="SRC-TEST", created_by="analyst", db_path=db)
    with foundation._connect(db) as con:
        row = con.execute("SELECT official_id,id_status,official_id_issuer FROM institution WHERE tedt_institution_id=?", (ident,)).fetchone()
    assert row["official_id"] == "MEN-001"
    assert row["id_status"] == "official_verified"
    assert row["official_id_issuer"] == "Ministère de l'Éducation"
    with pytest.raises(Exception):
        foundation.register_official_institution("MEN-001", "Ministère de l'Éducation", "École doublon", source_id="SRC-TEST", created_by="analyst", db_path=db)


def test_reference_seed_loads_provisional_indicators_and_sources(tmp_path):
    db = tmp_path / "foundation.sqlite"
    counts = foundation.seed_reference_files(db)
    assert counts["sources"] >= 1
    assert counts["indicators"] >= 1
    with foundation._connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM source").fetchone()[0] >= 1
        assert con.execute("SELECT COUNT(*) FROM indicator_dictionary").fetchone()[0] >= 1


def test_staging_integrity_check_detects_modified_original(tmp_path):
    db = _setup(tmp_path)
    raw = b"governorate,rate\nTunis,97.2\n"
    result = foundation.ingest_file("pilot.csv", raw, _metadata(), base_dir=tmp_path, db_path=db)
    with open(result["raw_path"], "wb") as f:
        f.write(raw + b"# altered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        foundation.load_batch_frame(result["batch_id"], base_dir=tmp_path, db_path=db)


def test_synthetic_lot1_pilot_is_explicitly_non_official():
    from tedt_core.foundation_demo import make_schooling_demo
    demo = make_schooling_demo()
    assert len(demo) == 24
    assert set(demo["value_origin"]) == {"synthetic_demo_only"}
    assert set(demo["reference_period"]) == {"DEMO_ONLY_NOT_RGPH2024"}
    assert demo["schooling_rate_demo_pct"].between(91, 99.5).all()


def test_synthetic_lot1_pilot_is_reproducible():
    from tedt_core.foundation_demo import make_schooling_demo
    pd.testing.assert_frame_equal(make_schooling_demo(), make_schooling_demo())
