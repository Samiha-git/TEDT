import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tedt_core import assistant, data_store, diagnostics, early_warning, metrics, scenario_store, synthetic  # noqa: E402
from tedt_core.config import GOVERNORATES, REFERENCE_AGGREGATES as REF, normalize_governorate  # noqa: E402


# ---------------------------------------------------------------- metrics
def test_gini_equal_is_zero():
    assert metrics.weighted_gini([5, 5, 5, 5], [1, 2, 3, 4]) == pytest.approx(0.0, abs=1e-12)


def test_gini_known_value():
    # two units, values 0 and 1, equal weights -> Gini = 0.5 (trapezoid Lorenz)
    assert metrics.weighted_gini([0, 1], [1, 1]) == pytest.approx(0.5)


def test_gini_weights_equivalent_to_replication():
    a = metrics.weighted_gini([1, 2, 3], [1, 2, 1])
    b = metrics.weighted_gini([1, 2, 2, 3], None)
    assert a == pytest.approx(b)


def test_weighted_mean():
    assert metrics.weighted_mean([10, 20], [1, 3]) == pytest.approx(17.5)


def test_top_bottom_gap_simple():
    # 4 equal-weight units; bottom quartile = 1, top quartile = 4
    assert metrics.top_bottom_gap([1, 2, 3, 4], [1, 1, 1, 1], 0.25) == pytest.approx(3.0)


def test_top_bottom_gap_fractional_units():
    # weights 1,1 and share .25 -> only half of each unit counts; values 0 and 10 -> gap 10
    assert metrics.top_bottom_gap([0, 10], [1, 1], 0.25) == pytest.approx(10.0)


def test_lorenz_endpoints():
    x, y = metrics.lorenz_curve([1, 2, 3], [1, 1, 1])
    assert (x[0], y[0]) == (0, 0) and x[-1] == pytest.approx(1) and y[-1] == pytest.approx(1)


# ---------------------------------------------------------------- config
def test_24_governorates_match_geojson():
    names = {f["properties"]["shapeName"] for f in data_store.geojson()["features"]}
    assert set(GOVERNORATES) == names and len(names) == 24


@pytest.mark.parametrize("raw,exp", [("Le Kef", "El Kef"), ("الكاف", "El Kef"), ("Gabes", "Gabès"), ("gouvernorat de Béja", "Béja"), ("ولاية تونس", "Tunis"), ("Medenine", "Médenine"), ("Kebili", "Kébili"), ("Atlantis", None)])
def test_normalize_governorate(raw, exp):
    assert normalize_governorate(raw) == exp


# ---------------------------------------------------------------- synthetic data
def test_synthetic_is_deterministic_and_calibrated():
    b = data_store.synthetic_bundle()
    tot = b.institutions[["pupils", "teachers", "classes"]].sum()
    assert len(b.institutions) == REF["institutions_total"]
    assert abs(tot["pupils"] - REF["pupils_total"]) / REF["pupils_total"] < 0.001
    assert abs(tot["teachers"] - REF["teachers_total"]) / REF["teachers_total"] < 0.002
    ctx2 = synthetic.make_context()
    pd.testing.assert_frame_equal(ctx2, b.context)
    assert b.institutions["institution_id"].str.startswith("SYN-").all()


def test_synthetic_ranges():
    b = data_store.synthetic_bundle()
    i = b.institutions
    assert i["equipment_index"].between(0, 1).all() and i["dropout_rate"].between(0, 1).all()
    assert b.students["sex"].isin(["F", "M"]).all() and "name" not in b.students.columns


# ---------------------------------------------------------------- data store / validation
def _good_inst():
    return pd.DataFrame({"Governorate": ["Tunis", "الكاف", "Sfax"], "Level": ["primary", "secondary", "primary"], "pupils": [100, 200, 300],
                         "teachers": [10, 15, 20], "classes": [4, 8, 12], "equipment_index": [0.5, 0.7, 1.4]})


def test_validate_ok_and_cleaning():
    rep = data_store.validate_dataset("institutions", _good_inst())
    assert rep.ok
    assert set(rep.clean["governorate"]) == {"Tunis", "El Kef", "Sfax"}
    assert rep.clean["equipment_index"].isna().sum() == 1  # 1.4 out of range -> NaN
    assert any("outside" in w for w in rep.warnings)


def test_validate_missing_column():
    rep = data_store.validate_dataset("institutions", _good_inst().drop(columns=["teachers"]))
    assert not rep.ok and "teachers" in rep.errors[0]


def test_validate_drops_bad_rows():
    df = _good_inst()
    df.loc[0, "Governorate"] = "Atlantis"
    df.loc[1, "pupils"] = -5
    rep = data_store.validate_dataset("institutions", df)
    assert rep.ok and len(rep.clean) == 1


def test_governorate_table_aggregation_exact():
    inst = pd.DataFrame({"governorate": ["Tunis", "Tunis", "Sfax"], "level": ["primary"] * 3, "pupils": [100, 300, 200], "teachers": [10, 20, 10],
                         "classes": [4, 12, 8], "equipment_index": [0.2, 0.6, 0.5]})
    ctx = pd.DataFrame({"governorate": ["Tunis", "Sfax"], "deprivation_index": [0.3, 0.6], "rural_share": [0.1, 0.5]})
    g = data_store.governorate_table(inst, ctx).set_index("governorate")
    assert g.loc["Tunis", "pupils"] == 400 and g.loc["Tunis", "class_size"] == pytest.approx(25.0)
    assert g.loc["Tunis", "equipment_index"] == pytest.approx((0.2 * 100 + 0.6 * 300) / 400)  # pupil-weighted


def test_catalog_integrity():
    cat = data_store.load_catalog()
    assert cat["status"].isin([1, 2, 3, 4]).all() and cat["id"].is_unique
    assert (cat[cat["status"] == 1]["url"].fillna("") != "").all()  # status 1 must carry a source URL
    r = data_store.readiness_index(cat)
    assert 0 < r < 100


def test_readiness_index_formula():
    df = pd.DataFrame({"status": [1, 2, 3, 4]})
    assert data_store.readiness_index(df) == pytest.approx((1 + 0.6 + 0.25 + 0) / 4 * 100)


# ---------------------------------------------------------------- diagnostics
def test_alignment_identical_and_disjoint():
    p = pd.Series([0.5, 0.5, 0, 0, 0, 0], index=diagnostics.BLOOM_KEYS)
    q = pd.Series([0, 0, 0, 0, 0.5, 0.5], index=diagnostics.BLOOM_KEYS)
    assert diagnostics.alignment_index(p, p) == pytest.approx(1.0)
    assert diagnostics.alignment_index(p, q) == pytest.approx(0.0)


def test_bloom_distribution_sums_to_one_and_has_six_levels():
    items = pd.DataFrame({"bloom_level": ["remember", "apply", "apply"], "points": [1, 2, 1]})
    d = diagnostics.bloom_distribution(items)
    assert len(d) == 6 and d.sum() == pytest.approx(1.0) and d["apply"] == pytest.approx(0.75)


def test_cognitive_demand():
    p = pd.Series([1, 0, 0, 0, 0, 0], index=diagnostics.BLOOM_KEYS)
    assert diagnostics.cognitive_demand(p) == 1.0


# ---------------------------------------------------------------- early warning
@pytest.fixture(scope="module")
def ews():
    b = data_store.synthetic_bundle()
    return b, early_warning.train(b.students)


def test_ews_learns_something_and_is_calibrated(ews):
    _b, m = ews
    assert m.auc > 0.65
    assert abs(m.calibration["predicted"].mean() - m.calibration["observed"].mean()) < 0.02


def test_ews_signs_match_declared_rule(ews):
    _b, m = ews
    c = m.coefficients.set_index("feature")["std_coef"]
    assert c["absence_rate"] > 0 and c["ses_index"] < 0 and c["prior_score"] < 0


def test_ews_small_cell_suppression(ews):
    b, m = ews
    few = b.students.groupby("governorate").head(10)  # 10 rows per governorate -> all suppressed at 30
    agg = early_warning.aggregate_risk(m, few)
    assert agg["suppressed"].all() and agg["mean_risk"].isna().all()


def test_ews_profile_monotone(ews):
    _b, m = ews
    base = dict(ses_index=0.0, absence_rate=0.05, repetitions=0, prior_score=55, class_size=25, distance_km=2.0, rural=0, level="primary")
    r0, _ = early_warning.predict_profile(m, base)
    r1, _ = early_warning.predict_profile(m, {**base, "absence_rate": 0.3})
    assert r1 > r0


def test_fairness_audit_columns(ews):
    _b, m = ews
    a = early_warning.fairness_audit(m, 0.1)
    assert {"attribute", "group", "recall_tpr", "false_positive_rate"} <= set(a.columns) and set(a["attribute"]) == {"sex", "rural"}


# ---------------------------------------------------------------- scenario store
def test_scenario_store_roundtrip(tmp_path):
    p = tmp_path / "t.sqlite"
    scenario_store.save("a", {"class_size_reduction": 0.1}, {"eps_class": 10}, {"delta_quality": 1.5}, "synthetic", path=p)
    df = scenario_store.list_all(path=p)
    assert len(df) == 1 and df.loc[0, "name"] == "a" and df.loc[0, "delta_quality"] == 1.5
    scenario_store.delete_all(path=p)
    assert scenario_store.list_all(path=p).empty


# ---------------------------------------------------------------- assistant
def test_assistant_intents_and_sources():
    b = data_store.synthetic_bundle()
    ctx = {"gov": b.governorates(), "catalog": data_store.load_catalog(), "synthetic": True, "last_sim": None}
    be = assistant.RuleBasedBackend()
    for q in ["ما الولايات التي تسجل أكبر تفاوت في الموارد التعليمية؟", "Quels gouvernorats présentent le plus d'inégalités ?"]:
        assert be.answer(q, "ar", ctx).text.count("- ") >= 5
    assert "[" in be.answer("ما مصادر البيانات التي ما زالت غير متوفرة؟", "ar", ctx).text
    ind = be.answer("ما أهم المؤشرات التي يجب أن يراقبها المجلس؟", "ar", ctx)
    assert len(ind.sources) == 7
    assert "لم يُشغَّل" in be.answer("ما أثر تخفيف الاكتظاظ وفق السيناريو المختار؟", "ar", ctx).text
    unknown = be.answer("zzzz qqqq", "fr", ctx)
    assert "sans modèle de langage" in unknown.text and unknown.sources == []
