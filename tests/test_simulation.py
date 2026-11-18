import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tedt_core import data_store  # noqa: E402
from tedt_core import simulation as sim  # noqa: E402


@pytest.fixture(scope="module")
def gov():
    return data_store.synthetic_bundle().governorates()


def toy(deprivation=(0.2, 0.8)):
    return pd.DataFrame({
        "governorate": ["Tunis", "Sfax"], "name_fr": ["Tunis", "Sfax"], "name_ar": ["تونس", "صفاقس"],
        "pupils": [1000.0, 1000.0], "teachers": [50.0, 50.0], "classes": [40.0, 40.0], "class_size": [25.0, 25.0], "ptr": [20.0, 20.0],
        "equipment_index": [0.5, 0.5], "quality": [50.0, 50.0], "dropout": [0.10, 0.10], "deprivation_index": list(deprivation),
    })


def test_baseline_changes_nothing(gov):
    r = sim.run_scenario(gov, sim.Scenario())
    assert r.national["delta_quality"] == pytest.approx(0, abs=1e-12)
    assert r.costs["horizon_total_um"] == 0
    assert "baseline" in r.warnings
    assert np.allclose(r.gov["quality"], r.gov["quality_after"])


def test_class_size_reduction_arithmetic():
    g = toy()
    r = sim.run_scenario(g, sim.Scenario(class_size_reduction=0.2)).gov.set_index("governorate")
    # x=0.2 -> classes x 1/(1-x) = 1.25 ; size 25 -> 20
    assert r.loc["Tunis", "class_size_after"] == pytest.approx(20.0)
    assert r.loc["Tunis", "added_classrooms"] == pytest.approx(40 * 0.2 / 0.8)
    assert r.loc["Tunis", "added_teachers"] == pytest.approx(50 * 0.2 / 0.8)
    # teachers scale with classes (constant teacher/class ratio) -> PTR falls by the same factor 1-x
    assert r.loc["Tunis", "ptr_after"] == pytest.approx(16.0)


def test_quality_formula_by_hand():
    g = toy(deprivation=(0.4, 0.4))
    asm = sim.Assumptions(eps_class=10, eps_ptr=6, eps_equip=8, gamma_disadv=0.5, kappa_dropout=0.1)
    r = sim.run_scenario(g, sim.Scenario(class_size_reduction=0.2), asm).gov.iloc[0]
    expected = (1 + 0.5 * 0.4) * (10 * math.log(25 / 20) + 6 * math.log(20 / 16))  # class-size AND PTR terms
    assert r["delta_quality"] == pytest.approx(expected)
    assert r["dropout_after"] == pytest.approx(0.10 * math.exp(-0.1 * expected / 10))


def test_equipment_saturation_and_bounds():
    g = toy()
    big = sim.run_scenario(g, sim.Scenario(equipment_budget_um=1e9)).gov
    assert (big["equipment_after"] <= 1).all() and (big["equipment_after"] > 0.99).all()
    assert (big["quality_after"] <= 100).all()
    one = sim.run_scenario(g, sim.Scenario(equipment_budget_um=1000, equity_weight=0)).gov.iloc[0]
    # equal pupils, lam=0 -> each gets 500 ; per 1000 pupils = 500 ; E' = 1-(0.5)exp(-0.1*500)
    assert one["equipment_after"] == pytest.approx(1 - 0.5 * math.exp(-0.1 * 500))


def test_allocation_weights_sum_to_one_and_equity_shifts_to_need():
    g = toy(deprivation=(0.2, 0.8))
    a0 = sim.allocation_weights(g, 0.0, None)
    a1 = sim.allocation_weights(g, 1.0, None)
    assert a0.sum() == pytest.approx(1) and a1.sum() == pytest.approx(1)
    assert a0[0] == pytest.approx(0.5) and a1[1] == pytest.approx(0.8)  # share proportional to need


def test_scope_restricts_effects():
    g = toy()
    r = sim.run_scenario(g, sim.Scenario(class_size_reduction=0.2, extra_teachers_pct=5, equipment_budget_um=100, scope=("Tunis",))).gov.set_index("governorate")
    assert r.loc["Sfax", "delta_quality"] == 0 and r.loc["Sfax", "added_teachers"] == 0 and r.loc["Sfax", "equipment_budget_um"] == 0
    assert r.loc["Tunis", "delta_quality"] > 0


def test_extra_teachers_total_equals_pct_of_stock(gov):
    r = sim.run_scenario(gov, sim.Scenario(extra_teachers_pct=3))
    assert r.costs["teachers_added"] == pytest.approx(0.03 * gov["teachers"].sum())


def test_cost_accounting():
    g = toy()
    asm = sim.Assumptions(cost_teacher_um=1.0, cost_room_um=3.0, horizon_years=5)
    r = sim.run_scenario(g, sim.Scenario(class_size_reduction=0.2, equipment_budget_um=200), asm)
    dT, dC = 2 * 50 * 0.25, 2 * 40 * 0.25
    assert r.costs["recurring_um_per_year"] == pytest.approx(dT)
    assert r.costs["oneoff_um"] == pytest.approx(dC * 3 + 200)
    assert r.costs["horizon_total_um"] == pytest.approx(dT * 5 + dC * 3 + 200)


def test_monotonicity(gov):
    prev = -1
    for x in (0.0, 0.05, 0.1, 0.2, 0.3):
        q = sim.run_scenario(gov, sim.Scenario(class_size_reduction=x)).national["delta_quality"]
        assert q >= prev
        prev = q
    cost_prev = -1
    for b in (0, 1000, 5000):
        c = sim.run_scenario(gov, sim.Scenario(equipment_budget_um=b)).costs["horizon_total_um"]
        assert c >= cost_prev
        cost_prev = c


def test_equity_weight_reduces_inequality_for_targeted_equipment(gov):
    base = sim.run_scenario(gov, sim.Scenario(equipment_budget_um=8000, equity_weight=0)).national
    eq = sim.run_scenario(gov, sim.Scenario(equipment_budget_um=8000, equity_weight=1)).national
    assert eq["gini_quality_after"] <= base["gini_quality_after"] + 1e-12


def test_zero_effect_params_give_zero_gain(gov):
    asm = sim.Assumptions(eps_class=0, eps_ptr=0, eps_equip=0)
    r = sim.run_scenario(gov, sim.Scenario(class_size_reduction=0.2, extra_teachers_pct=5, equipment_budget_um=5000), asm)
    assert r.national["delta_quality"] == pytest.approx(0, abs=1e-12) and r.costs["horizon_total_um"] > 0


def test_preset_scaling_scales_gain_linearly(gov):
    sc = sim.Scenario(class_size_reduction=0.1)
    d1 = sim.run_scenario(gov, sc, sim.Assumptions()).national["delta_quality"]
    d2 = sim.run_scenario(gov, sc, sim.Assumptions().scaled(2.0)).national["delta_quality"]
    assert d2 == pytest.approx(2 * d1, rel=1e-9)  # no clipping at these values


def test_monte_carlo_bands_contain_central_and_are_ordered(gov):
    sc = sim.Scenario(class_size_reduction=0.1, extra_teachers_pct=2, equipment_budget_um=3000, equity_weight=0.5)
    mc = sim.monte_carlo(gov, sc, n=400, seed=1)
    q = mc["delta_quality"]
    assert q["p10"] <= q["p50"] <= q["p90"] and q["p10"] >= 0
    central = sim.run_scenario(gov, sc).national["delta_quality"]
    assert q["p10"] <= central <= q["p90"]
    assert sim.monte_carlo(gov, sc, n=400, seed=1) == mc  # reproducible


def test_sensitivity_zero_param_removes_its_contribution(gov):
    sc = sim.Scenario(class_size_reduction=0.1)
    s = sim.sensitivity(gov, sc, sim.Assumptions(eps_ptr=0.0)).set_index("parameter")  # isolate the class-size term
    assert s.loc["eps_class", "at_zero"] == pytest.approx(0, abs=1e-12)  # only lever is class size
    assert s.loc["eps_class", "at_double"] == pytest.approx(2 * s.loc["eps_class", "central"])


def test_works_with_user_data_without_context(gov):
    inst = pd.DataFrame({"governorate": ["Tunis", "Sfax", "Sousse"] * 3, "level": ["primary"] * 9, "pupils": [100, 200, 150] * 3, "teachers": [8, 12, 10] * 3,
                         "classes": [4, 8, 6] * 3, "equipment_index": [0.3, 0.6, 0.5] * 3, "mean_score": [40, 55, 50] * 3, "dropout_rate": [0.1, 0.05, 0.07] * 3})
    g = data_store.governorate_table(inst, pd.DataFrame({"governorate": [], "deprivation_index": [], "rural_share": []}))
    assert g["deprivation_index"].between(0, 1).all()
    r = sim.run_scenario(g, sim.Scenario(class_size_reduction=0.1))
    assert r.national["delta_quality"] > 0
