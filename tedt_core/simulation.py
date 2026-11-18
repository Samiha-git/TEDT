"""Education policy simulation engine (Engine 4).

IMPORTANT - scientific status
-----------------------------
This is a *transparent parametric simulation*, not a statistical estimate calibrated on real data.
The elasticities below are placeholders that the user can edit; they must be replaced by values
estimated on Tunisian panel data (ideally with a causal design) before any quantitative claim is made.
The Monte-Carlo band only propagates the *declared* parameter ranges; it is not a confidence interval.

Model (per governorate g; P pupils, C classes, T teachers, E equipment index in [0,1],
Q quality index 0-100, D drop-out rate, n_g need index in [0,1])
--------------------------------------------------------------------------------------------------
Allocation weight  a_g  = (1-lam)*P_g/sum(P) + lam*P_g*n_g/sum(P*n), restricted to the scope and renormalised.
Lever A (class size -x):   dC_g = C_g * x/(1-x)    ; dT_A = dC_g * T_g/C_g  ; dRooms = dC_g      (g in scope)
Lever B (extra teachers):  dT_B = a_g * (pct/100) * sum(T)
Lever C (equipment budget B): E'_g = 1 - (1-E_g)*exp(-k * a_g*B / (P_g/1000))
After:  C' = C+dC ; T' = T+dT_A+dT_B ; s' = P/C' ; PTR' = P/T'
dQ_g = (1 + gamma*n_g) * ( eps_c*ln(s/s') + eps_p*ln(PTR/PTR') + eps_e*(E'-E) )
Q' = clip(Q+dQ, 0, 100)  ;  D' = D*exp(-kappa*dQ/10)
Effects of class size, pupil-teacher ratio and equipment are ADDITIVE partial effects. A class-size cut that creates
classes and teachers at constant teacher/class ratio lowers both class size and PTR, so both terms apply:
the eps values must be read as partial effects (this is an assumption, not an estimate).
Costs (in UM = one teacher-year): recurring = (dT_A+dT_B)*c_t ; one-off = dRooms*c_r + B ;
horizon total = recurring*H + one-off.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .metrics import top_bottom_gap, weighted_gini, weighted_mean
from .missing_data import apply_missing_policy


@dataclass
class Scenario:
    class_size_reduction: float = 0.0   # share in [0, 0.5): x
    extra_teachers_pct: float = 0.0     # % of national teacher stock
    equipment_budget_um: float = 0.0    # one-off, in UM (teacher-years)
    equity_weight: float = 0.0          # lam in [0,1]: 0 = proportional to pupils, 1 = proportional to need
    scope: tuple[str, ...] | None = None  # governorates concerned (None = all)

    def is_baseline(self) -> bool:
        return self.class_size_reduction == 0 and self.extra_teachers_pct == 0 and self.equipment_budget_um == 0


@dataclass
class Assumptions:
    eps_class: float = 10.0      # quality points per ln-unit of class-size reduction
    eps_ptr: float = 6.0         # quality points per ln-unit of pupil-teacher-ratio reduction
    eps_equip: float = 8.0       # quality points per +1.0 of equipment index
    gamma_disadv: float = 0.5    # amplification of effects with need
    kappa_dropout: float = 0.10  # drop-out elasticity to quality change (per 10 points)
    equip_k: float = 0.10        # saturation speed of equipment investment (per UM per 1000 pupils)
    cost_teacher_um: float = 1.0
    cost_room_um: float = 3.0
    horizon_years: int = 5
    teacher_cost_tnd: float = 0.0  # optional conversion of 1 UM to TND; 0 = not provided

    def scaled(self, factor: float) -> "Assumptions":
        d = asdict(self)
        for k in ("eps_class", "eps_ptr", "eps_equip"):
            d[k] *= factor
        return Assumptions(**d)


PRESETS = {"prudent": 0.5, "central": 1.0, "optimistic": 1.5}


@dataclass
class SimulationResult:
    gov: pd.DataFrame
    national: dict
    costs: dict
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------------------
def _need(gov: pd.DataFrame) -> np.ndarray:
    return np.clip(gov["deprivation_index"].to_numpy(float), 0.05, 1.0)


def allocation_weights(gov: pd.DataFrame, equity_weight: float, scope) -> np.ndarray:
    P = gov["pupils"].to_numpy(float)
    n = _need(gov)
    lam = float(np.clip(equity_weight, 0, 1))
    w = (1 - lam) * P / P.sum() + lam * (P * n) / (P * n).sum()
    if scope:
        mask = gov["governorate"].isin(scope).to_numpy()
        w = w * mask
    s = w.sum()
    return w / s if s > 0 else np.zeros_like(w)


def scope_mask(gov: pd.DataFrame, scope) -> np.ndarray:
    if not scope:
        return np.ones(len(gov), dtype=bool)
    return gov["governorate"].isin(scope).to_numpy()


def _core(gov: pd.DataFrame, sc: Scenario, p: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Vectorised over parameter draws: p[name] has shape (n,1); outputs have shape (n,G)."""
    required = ["pupils", "classes", "teachers", "equipment_index", "quality", "dropout", "deprivation_index"]
    gov, _audit = apply_missing_policy(gov, required, strategy="none")
    P = gov["pupils"].to_numpy(float)
    C = gov["classes"].to_numpy(float)
    T = gov["teachers"].to_numpy(float)
    E = gov["equipment_index"].to_numpy(float)
    Q = gov["quality"].to_numpy(float)
    D = gov["dropout"].to_numpy(float)
    need = _need(gov)
    a = allocation_weights(gov, sc.equity_weight, sc.scope)
    mask = scope_mask(gov, sc.scope).astype(float)
    x = float(np.clip(sc.class_size_reduction, 0, 0.9))

    dC = C * x / (1 - x) * mask
    dT_A = T * x / (1 - x) * mask
    dT_B = a * (sc.extra_teachers_pct / 100.0) * T.sum()
    budget = a * sc.equipment_budget_um
    b_per_1000 = budget / (P / 1000.0)
    E2 = 1 - (1 - E) * np.exp(-p["equip_k"] * b_per_1000)

    C2, T2 = C + dC, T + dT_A + dT_B
    s, s2 = P / C, P / C2
    ptr, ptr2 = P / T, P / T2
    dq = (1 + p["gamma"] * need) * (
        p["eps_c"] * np.log(s / s2) + p["eps_p"] * np.log(ptr / ptr2) + p["eps_e"] * (E2 - E)
    )
    Q2 = np.clip(Q + dq, 0, 100)
    dq_eff = Q2 - Q
    D2 = np.clip(D * np.exp(-p["kappa"] * dq_eff / 10.0), 0, 1)
    return {"dq": dq_eff, "Q2": Q2, "D2": D2, "E2": E2, "C2": C2, "T2": T2, "dC": dC, "dT": dT_A + dT_B,
            "dT_A": dT_A, "dT_B": dT_B, "budget": budget, "s2": s2, "ptr2": ptr2}


def _row(a: np.ndarray) -> np.ndarray:
    """First parameter draw as a 1-D array over governorates (outputs mix (G,) and (n,G) shapes)."""
    a = np.asarray(a, dtype=float)
    return a if a.ndim == 1 else a[0]


def _params(asm: Assumptions) -> dict[str, np.ndarray]:
    one = lambda v: np.array([[float(v)]])  # noqa: E731
    return {"eps_c": one(asm.eps_class), "eps_p": one(asm.eps_ptr), "eps_e": one(asm.eps_equip),
            "gamma": one(asm.gamma_disadv), "kappa": one(asm.kappa_dropout), "equip_k": one(asm.equip_k)}


def run_scenario(gov: pd.DataFrame, sc: Scenario, asm: Assumptions | None = None) -> SimulationResult:
    asm = asm or Assumptions()
    gov = gov.reset_index(drop=True)
    out = _core(gov, sc, _params(asm))
    P = gov["pupils"].to_numpy(float)
    res = gov[["governorate", "name_fr", "name_ar", "pupils", "teachers", "classes", "class_size", "ptr",
               "equipment_index", "quality", "dropout", "deprivation_index"]].copy()
    res["class_size_after"] = _row(out["s2"])
    res["ptr_after"] = _row(out["ptr2"])
    res["equipment_after"] = _row(out["E2"])
    res["quality_after"] = _row(out["Q2"])
    res["delta_quality"] = _row(out["dq"])
    res["dropout_after"] = _row(out["D2"])
    res["added_teachers"] = _row(out["dT"])
    res["added_classrooms"] = _row(out["dC"])
    res["equipment_budget_um"] = _row(out["budget"])
    rec = _row(out["dT"]) * asm.cost_teacher_um
    one_off = _row(out["dC"]) * asm.cost_room_um + _row(out["budget"])
    res["cost_horizon_um"] = rec * asm.horizon_years + one_off
    res["cost_per_pupil_um"] = res["cost_horizon_um"] / P

    Q, Q2 = res["quality"].to_numpy(float), res["quality_after"].to_numpy(float)
    D, D2 = res["dropout"].to_numpy(float), res["dropout_after"].to_numpy(float)
    national = {
        "quality_before": weighted_mean(Q, P), "quality_after": weighted_mean(Q2, P),
        "dropout_before": weighted_mean(D, P), "dropout_after": weighted_mean(D2, P),
        "gini_quality_before": weighted_gini(Q, P), "gini_quality_after": weighted_gini(Q2, P),
        "gap_before": top_bottom_gap(Q, P), "gap_after": top_bottom_gap(Q2, P),
        "ptr_before": P.sum() / gov["teachers"].sum(), "ptr_after": P.sum() / (gov["teachers"] + _row(out["dT"])).sum(),
        "class_size_before": P.sum() / gov["classes"].sum(), "class_size_after": P.sum() / (gov["classes"] + _row(out["dC"])).sum(),
        "equipment_before": weighted_mean(res["equipment_index"], P),
        "equipment_after": weighted_mean(res["equipment_after"], P),
    }
    national["delta_quality"] = national["quality_after"] - national["quality_before"]
    national["delta_dropout_rel"] = (national["dropout_after"] / national["dropout_before"] - 1) if national["dropout_before"] else 0.0
    recurring = float(rec.sum())
    costs = {
        "teachers_added": float(_row(out["dT"]).sum()), "classrooms_added": float(_row(out["dC"]).sum()),
        "recurring_um_per_year": recurring, "oneoff_um": float(one_off.sum()),
        "horizon_total_um": recurring * asm.horizon_years + float(one_off.sum()),
        "horizon_years": asm.horizon_years,
    }
    costs["per_pupil_um"] = costs["horizon_total_um"] / P.sum()
    costs["um_per_quality_point"] = (costs["horizon_total_um"] / national["delta_quality"]) if national["delta_quality"] > 1e-9 else float("nan")
    if asm.teacher_cost_tnd > 0:
        costs["horizon_total_tnd"] = costs["horizon_total_um"] * asm.teacher_cost_tnd
    warns = []
    if sc.class_size_reduction > 0.3:
        warns.append("class_size_extrapolation")
    if sc.scope and len(sc.scope) < len(gov):
        warns.append("scoped")
    if sc.is_baseline():
        warns.append("baseline")
    return SimulationResult(res, national, costs, warns)


def monte_carlo(gov: pd.DataFrame, sc: Scenario, asm: Assumptions | None = None, n: int = 1000, seed: int = 0) -> dict:
    """Propagate declared parameter ranges U(0, 2*central) for the effect parameters.
    Includes the possibility of a null effect. NOT a confidence interval."""
    asm = asm or Assumptions()
    gov = gov.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    u = lambda c: rng.uniform(0, 2 * c, size=(n, 1))  # noqa: E731
    p = {"eps_c": u(asm.eps_class), "eps_p": u(asm.eps_ptr), "eps_e": u(asm.eps_equip),
         "gamma": u(asm.gamma_disadv), "kappa": u(asm.kappa_dropout), "equip_k": np.full((n, 1), asm.equip_k)}
    out = _core(gov, sc, p)
    P = gov["pupils"].to_numpy(float)
    required = ["pupils", "classes", "teachers", "equipment_index", "quality", "dropout", "deprivation_index"]
    gov, _audit = apply_missing_policy(gov, required, strategy="none")
    Q = gov["quality"].to_numpy(float)
    D = gov["dropout"].to_numpy(float)
    w = P / P.sum()
    dq_nat = out["dq"] @ w
    drop_rel = (out["D2"] @ w) / (D @ w) - 1
    g0 = weighted_gini(Q, P)
    gini_delta = np.array([weighted_gini(out["Q2"][i], P) - g0 for i in range(n)])
    pct = lambda a: {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90))}  # noqa: E731
    return {"delta_quality": pct(dq_nat), "delta_dropout_rel": pct(drop_rel), "delta_gini": pct(gini_delta),
            "mean_delta_quality": float(dq_nat.mean()), "n": n}


def sensitivity(gov: pd.DataFrame, sc: Scenario, asm: Assumptions | None = None) -> pd.DataFrame:
    """One-at-a-time sensitivity of the national quality gain: each effect parameter set to 0 and to 2x its central value."""
    asm = asm or Assumptions()
    rows = []
    base = run_scenario(gov, sc, asm).national["delta_quality"]
    for name in ("eps_class", "eps_ptr", "eps_equip", "gamma_disadv"):
        lo = asdict(asm); lo[name] = 0.0
        hi = asdict(asm); hi[name] = getattr(asm, name) * 2
        rows.append((name, run_scenario(gov, sc, Assumptions(**lo)).national["delta_quality"],
                     run_scenario(gov, sc, Assumptions(**hi)).national["delta_quality"], base))
    return pd.DataFrame(rows, columns=["parameter", "at_zero", "at_double", "central"])
