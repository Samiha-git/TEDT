"""SQLite scenario persistence with reproducibility metadata and local audit events.

This local store is protected by filesystem permissions, not institutional identity
management. It is not a substitute for authenticated multi-user access control.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from .config import DB_PATH

MODEL_VERSION = "tedt-parametric-simulation-v1"


def _conn(path=None):
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute(
        "CREATE TABLE IF NOT EXISTS scenarios (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, name TEXT,"
        " data_provenance TEXT, scenario_json TEXT, assumptions_json TEXT, results_json TEXT)"
    )
    cols = {row[1] for row in con.execute("PRAGMA table_info(scenarios)")}
    for name, declaration in (("source_fingerprint", "TEXT NOT NULL DEFAULT ''"),
                              ("random_seed", "INTEGER NOT NULL DEFAULT 7"),
                              ("model_version", "TEXT NOT NULL DEFAULT 'legacy'"),
                              ("actor", "TEXT NOT NULL DEFAULT 'local-unverified'")):
        if name not in cols:
            con.execute(f"ALTER TABLE scenarios ADD COLUMN {name} {declaration}")
    con.execute("CREATE TABLE IF NOT EXISTS scenario_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, event_at TEXT, action TEXT, scenario_id INTEGER, actor TEXT, details TEXT)")
    con.commit()
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return con


def save(name: str, scenario: dict, assumptions: dict, results: dict, provenance: str,
         path=None, source_fingerprint: str = "", random_seed: int = 7,
         model_version: str = MODEL_VERSION, actor: str = "local-unverified", role: str = "viewer") -> int:
    if provenance in {"real", "imported_unverified"} and role not in {"analyst", "admin"}:
        raise PermissionError("Saving scenarios on real data requires an authenticated analyst or admin role.")
    if not name or not name.strip():
        raise ValueError("Scenario name is required")
    with _conn(path) as con:
        cur = con.execute(
            "INSERT INTO scenarios (created_at, name, data_provenance, scenario_json, assumptions_json, results_json, source_fingerprint, random_seed, model_version, actor) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), name.strip(), provenance,
             json.dumps(scenario, ensure_ascii=False, sort_keys=True), json.dumps(assumptions, sort_keys=True),
             json.dumps(results, sort_keys=True), source_fingerprint, int(random_seed), model_version, actor),
        )
        scenario_id = int(cur.lastrowid)
        con.execute("INSERT INTO scenario_audit (event_at, action, scenario_id, actor, details) VALUES (?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), "save", scenario_id, actor,
                     json.dumps({"provenance": provenance, "fingerprint": source_fingerprint, "seed": random_seed, "model": model_version})))
        return scenario_id


def list_all(path=None) -> pd.DataFrame:
    with _conn(path) as con:
        rows = con.execute("SELECT id, created_at, name, data_provenance, scenario_json, assumptions_json, results_json, source_fingerprint, random_seed, model_version, actor FROM scenarios ORDER BY id DESC").fetchall()
    out = []
    for i, ts, name, prov, sj, aj, rj, fingerprint, seed, model, actor in rows:
        sc, res = json.loads(sj), json.loads(rj)
        out.append({"id": i, "created_at": ts, "name": name, "data": prov,
                    "source_fingerprint": fingerprint, "random_seed": seed, "model_version": model,
                    "actor": actor, **{f"sc_{k}": v for k, v in sc.items()}, **res, "assumptions": aj})
    return pd.DataFrame(out)


def audit_log(path=None) -> pd.DataFrame:
    with _conn(path) as con:
        rows = con.execute("SELECT id, event_at, action, scenario_id, actor, details FROM scenario_audit ORDER BY id DESC").fetchall()
    return pd.DataFrame(rows, columns=["id", "event_at", "action", "scenario_id", "actor", "details"])


def log_event(action: str, actor: str, details: dict | None = None, path=None) -> None:
    with _conn(path) as con:
        con.execute("INSERT INTO scenario_audit (event_at, action, scenario_id, actor, details) VALUES (?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), action, None, actor,
                     json.dumps(details or {}, ensure_ascii=False, sort_keys=True)))


def delete_all(path=None) -> None:
    """Administrative maintenance helper; not exposed in the application UI."""
    with _conn(path) as con:
        con.execute("DELETE FROM scenarios")
        con.execute("INSERT INTO scenario_audit (event_at, action, scenario_id, actor, details) VALUES (?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), "delete_all", None, "local-unverified", "{}"))
