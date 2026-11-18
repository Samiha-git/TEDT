"""Authorization seam for a trusted institutional identity provider.

This prototype intentionally does not implement login or authenticate users. A trusted
OIDC/SSO middleware must populate session_state['tedt_auth']; a client-editable role
selector is deliberately not provided.
"""
from __future__ import annotations

ROLES = {"viewer", "analyst", "admin"}
PERMISSIONS = {
    "viewer": {"read"},
    "analyst": {"read", "save_scenario", "import_aggregate"},
    "admin": {"read", "save_scenario", "import_aggregate", "manage_history", "manage_users"},
}


def identity(session_state) -> dict:
    raw = session_state.get("tedt_auth") if session_state is not None else None
    if not isinstance(raw, dict):
        return {"authenticated": False, "user_id": "anonymous", "role": "viewer", "provider": "none"}
    role = str(raw.get("role", "viewer")).lower()
    if role not in ROLES or not raw.get("user_id") or not raw.get("provider"):
        return {"authenticated": False, "user_id": "anonymous", "role": "viewer", "provider": "invalid"}
    return {"authenticated": True, "user_id": str(raw["user_id"]), "role": role, "provider": str(raw["provider"])}


def allowed(session_state, action: str) -> bool:
    ident = identity(session_state)
    return bool(ident["authenticated"] and action in PERMISSIONS[ident["role"]])
