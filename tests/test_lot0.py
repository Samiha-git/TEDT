import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tedt_core import data_store, missing_data, reports, scenario_store, simulation, metrics


def _institutions():
    return pd.DataFrame({
        "governorate": ["Tunis", "Sfax", "Sousse"],
        "level": ["primary", "primary", "secondary"],
        "pupils": [100, 200, 150], "teachers": [8, 12, 10], "classes": [4, 8, 6],
        "institution_id": ["TN-001", "TN-002", "TN-003"],
        "equipment_index": [0.3, 0.6, 0.5], "mean_score": [40, 55, 50], "dropout_rate": [0.1, 0.05, 0.07],
    })


def _results():
    return pd.DataFrame({"governorate": ["Tunis", "Sfax"], "year": [2025, 2025], "level": ["primary", "primary"],
                         "subject": ["math", "math"], "mean_score": [55, 60], "pass_rate": [0.6, 0.7], "candidate_count": [100, 200]})


def test_real_mode_never_fills_missing_datasets_with_synthetic():
    b = data_store.build_bundle({"institutions": _institutions()}, mode="REAL_DATA")
    assert b.mode == "REAL_DATA"
    assert b.provenance["institutions"] == "imported_unverified"
    assert b.provenance["results"] == "unavailable"
    assert b.provenance["students"] == "unavailable" and b.students.empty
    assert b.context.empty and b.results.empty


def test_demo_mode_ignores_real_overrides():
    b = data_store.build_bundle({"institutions": _institutions()}, mode="DEMONSTRATION")
    assert b.provenance["institutions"] == "synthetic"
    assert len(b.institutions) > len(_institutions())


def test_real_mode_revalidates_overrides_before_activation():
    bad = _institutions().drop(columns="teachers")
    b = data_store.build_bundle({"institutions": bad}, mode="REAL_DATA")
    assert b.provenance["institutions"] == "unavailable"
    assert b.institutions.empty


def test_quality_score_penalizes_missing_optional_and_rejected_rows():
    df = _institutions()
    df.loc[0, "equipment_index"] = np.nan
    df.loc[1, "pupils"] = -2
    rep = data_store.validate_dataset("institutions", df)
    assert rep.ok and rep.counts["rejected"] == 1
    assert rep.quality_score < 100
    assert rep.rejected["rejection_reason"].str.contains("non_positive").any()


def test_missing_required_column_never_scores_full_completeness():
    rep = data_store.validate_dataset("institutions", _institutions().drop(columns="teachers"))
    assert not rep.ok and rep.quality_score == 0
    assert (rep.completeness.loc[rep.completeness.column == "teachers", "status"] == "missing_column").all()
    assert "rejection_reason" in rep.rejected


def test_missing_invalid_and_not_applicable_are_counted_separately():
    df = _institutions()
    df["equipment_index"] = [None, "oops", "n/a"]
    rep = data_store.validate_dataset("institutions", df)
    assert rep.counts["missing"] >= 1
    assert rep.counts["invalid"] >= 1
    assert rep.counts["not_applicable"] >= 1


def test_duplicate_institution_ids_are_rejected():
    df = _institutions()
    df.loc[1, "institution_id"] = "TN-001"
    rep = data_store.validate_dataset("institutions", df)
    assert rep.ok and len(rep.clean) == 1
    assert (rep.rejected.rejection_reason == "duplicate_institution_id").sum() == 2


def test_duplicate_result_keys_and_candidate_count_validation():
    df = pd.concat([_results(), _results().iloc[[0]]], ignore_index=True)
    rep = data_store.validate_dataset("results", df)
    assert rep.ok and len(rep.clean) == 1
    assert "duplicate_result_key" in set(rep.rejected.rejection_reason)
    df = _results(); df.loc[0, "candidate_count"] = 0
    rep = data_store.validate_dataset("results", df)
    assert "invalid_candidate_count" in set(rep.rejected.rejection_reason)


def test_missing_policy_blocks_by_default_and_audits_explicit_median():
    df = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
    with pytest.raises(ValueError, match="Missing required"):
        missing_data.apply_missing_policy(df, ["x"])
    out, audit = missing_data.apply_missing_policy(df, ["x"], strategy="median")
    assert out.x.tolist() == [1.0, 2.0, 3.0]
    assert audit.cells_imputed == 1 and audit.proportion_imputed == pytest.approx(1/3)


def test_simulation_blocks_missing_values_instead_of_imputing():
    gov = data_store.synthetic_bundle().governorates().head(4).copy()
    gov.loc[gov.index[0], "quality"] = np.nan
    with pytest.raises(ValueError, match="Missing required"):
        simulation.run_scenario(gov, simulation.Scenario(class_size_reduction=0.1))


def test_distribution_metrics_reject_missing_data():
    with pytest.raises(ValueError, match="complete finite"):
        metrics.weighted_gini([1, np.nan, 3], [1, 1, 1])
    assert metrics.weighted_mean([1, np.nan, 3], [1, 1, 1]) == pytest.approx(2.0)


def test_csv_export_has_mode_and_provenance_headers():
    data = data_store.export_frame(pd.DataFrame({"x": [1]}), "DEMONSTRATION", {"institutions": "synthetic"}, ("institutions",))
    first = data.decode("utf-8-sig").splitlines()[0]
    assert "__tedt_mode" in first and "__tedt_provenance" in first and "__tedt_warning" in first
    assert "SYNTHETIC_DEMONSTRATION_NOT_REAL" in data.decode("utf-8-sig")


def test_scenario_history_stores_reproducibility_metadata_and_audit(tmp_path):
    db = tmp_path / "scenarios.sqlite"
    scenario_store.save("repeatable", {"x": 0.1}, {"eps": 2}, {"delta_quality": 1.0}, "synthetic",
                        path=db, source_fingerprint="abc123", random_seed=19)
    hist = scenario_store.list_all(path=db)
    assert hist.loc[0, "source_fingerprint"] == "abc123"
    assert hist.loc[0, "random_seed"] == 19
    assert hist.loc[0, "model_version"] == scenario_store.MODEL_VERSION
    assert scenario_store.audit_log(path=db).iloc[0]["action"] == "save"


def test_french_pdf_export_produces_pdf_when_reportlab_available():
    if not reports.pdf_available("fr"):
        pytest.skip("ReportLab/font unavailable")
    gov = data_store.synthetic_bundle().governorates().head(5)
    lines = reports.insights(gov, "fr", True, None)
    pdf = reports.build_pdf(gov, "fr", True, None, lines, provenance={"institutions": "synthetic"}, mode="DEMONSTRATION")
    assert pdf.startswith(b"%PDF")


def test_arabic_pdf_dependency_failure_is_explicit():
    if reports.pdf_available("ar"):
        gov = data_store.synthetic_bundle().governorates().head(5)
        pdf = reports.build_pdf(gov, "ar", True, None, reports.insights(gov, "ar", True))
        assert pdf.startswith(b"%PDF")
    else:
        assert not reports.pdf_available("ar")
        gov = data_store.synthetic_bundle().governorates().head(5)
        with pytest.raises(RuntimeError, match="Arabic PDF requires"):
            reports.build_pdf(gov, "ar", True, None, reports.insights(gov, "ar", True))


def test_real_scenario_save_requires_authenticated_analyst_or_admin(tmp_path):
    db = tmp_path / "secure.sqlite"
    with pytest.raises(PermissionError):
        scenario_store.save("blocked", {}, {}, {}, "imported_unverified", path=db)
    scenario_store.save("allowed", {}, {}, {}, "imported_unverified", path=db, role="analyst", actor="analyst-1")
    assert scenario_store.list_all(path=db).iloc[0]["actor"] == "analyst-1"


def test_result_school_year_and_subject_are_validated():
    df = pd.concat([_results(), _results().iloc[[0]]], ignore_index=True)
    df["year"] = df["year"].astype(float)
    df.loc[0, "year"] = 2025.5
    df.loc[1, "subject"] = "unknown"
    rep = data_store.validate_dataset("results", df)
    assert rep.ok and len(rep.clean) == 1
    assert set(rep.rejected.rejection_reason) >= {"invalid_school_year", "invalid_subject"}


def test_governorate_aggregation_is_cycle_specific():
    inst = _institutions()
    ctx = pd.DataFrame({"governorate": [], "deprivation_index": [], "rural_share": []})
    all_levels = data_store.governorate_table(inst, ctx)
    primary = data_store.governorate_table(inst, ctx, "primary")
    assert all_levels["pupils"].sum() == 450
    assert primary["pupils"].sum() == 300
    assert set(primary["governorate"]) == {"Tunis", "Sfax"}


def test_real_mode_import_provenance_is_unverified_not_official():
    b = data_store.build_bundle({"institutions": _institutions()}, mode="REAL_DATA")
    assert b.provenance["institutions"] == "imported_unverified"


def test_duplicate_column_names_are_rejected_without_crashing():
    df = pd.DataFrame([["Tunis", "primary", 100, 10, 4, 1]],
                      columns=["governorate", "level", "pupils", "teachers", "classes", "classes"])
    rep = data_store.validate_dataset("institutions", df)
    assert not rep.ok and "Duplicate column names" in rep.errors[0]
    assert set(rep.rejected.rejection_reason) == {"duplicate_column_names"}


def test_governorate_coverage_is_explicit_and_never_assumes_national():
    partial = pd.DataFrame({"governorate": ["Tunis", "Sfax"]})
    coverage = data_store.governorate_coverage(partial)
    assert coverage["observed"] == 2
    assert coverage["expected"] == 24
    assert not coverage["complete"]
    full = pd.DataFrame({"governorate": list(data_store.GOVERNORATES)})
    assert data_store.governorate_coverage(full)["complete"]


def test_median_imputation_rejects_invalid_non_numeric_values():
    df = pd.DataFrame({"x": [1.0, "bad", np.nan]})
    with pytest.raises(ValueError, match="invalid non-numeric"):
        missing_data.apply_missing_policy(df, ["x"], strategy="median")


def test_real_mode_accepts_only_validated_aggregate_imports():
    inst = _institutions()
    results = _results()
    bundle = data_store.build_bundle({"institutions": inst, "results": results}, mode="REAL_DATA")
    assert bundle.provenance["institutions"] == "imported_unverified"
    assert bundle.provenance["results"] == "imported_unverified"
    assert bundle.provenance["students"] == "unavailable"
    assert len(bundle.students) == 0
