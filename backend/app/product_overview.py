from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from .learning import learning_summary
from .profile_registry import get_default_active_profile
from .retraining import latest_retraining_run, retraining_readiness


OVERVIEW_FORMAT = "prographer-photographer-profile-overview-v1"


def _safe_json(value: Any, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def photographer_profile_overview(
    conn: sqlite3.Connection,
    *,
    user_id: str,
) -> dict[str, Any]:
    """
    Small, stable, photographer-facing view of the AI Profile.

    This intentionally hides Dataset/MAE/CLIP/Recipe V1/V2/guards and all
    research-only details.  Diagnostics continue to exist through the older
    endpoints and UI, but normal product screens consume this overview.
    """
    registry = get_default_active_profile(conn, user_id=user_id)

    onboarding_row = conn.execute(
        """
        SELECT specialties_json,editor_software,style_words_json,priorities_json,
               notes,completed,updated_at
        FROM user_onboarding
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()

    onboarding = {
        "specialties": [],
        "editor_software": "",
        "style_words": [],
        "priorities": [],
        "notes": "",
        "completed": False,
        "updated_at": None,
    }
    if onboarding_row:
        onboarding = {
            "specialties": _safe_json(onboarding_row["specialties_json"], []),
            "editor_software": onboarding_row["editor_software"] or "",
            "style_words": _safe_json(onboarding_row["style_words_json"], []),
            "priorities": _safe_json(onboarding_row["priorities_json"], []),
            "notes": onboarding_row["notes"] or "",
            "completed": bool(onboarding_row["completed"]),
            "updated_at": onboarding_row["updated_at"],
        }

    if not registry or not registry.get("active_version"):
        return {
            "ok": True,
            "format": OVERVIEW_FORMAT,
            "profile_ready": False,
            "active_profile": None,
            "learning": {
                "sample_count": 0,
                "approved_count": 0,
                "corrected_count": 0,
                "acceptance_rate": None,
            },
            "growth": None,
            "candidate": None,
            "source": None,
            "photographer_preferences": onboarding,
        }

    active = registry["active_version"]
    learning = learning_summary(conn, user_id=user_id)
    readiness = retraining_readiness(
        conn,
        user_id=user_id,
        registry_id=registry["id"],
    )
    latest_run = latest_retraining_run(
        conn,
        user_id=user_id,
        registry_id=registry["id"],
    )

    source_row = conn.execute(
        """
        SELECT id,profile_name,catalog_name,status,created_at,updated_at
        FROM lightroom_profile_imports
        WHERE id=? AND user_id=?
        """,
        (registry["source_profile_import_id"], user_id),
    ).fetchone()

    candidate = None
    if latest_run and latest_run.get("candidate_version_id"):
        candidate_row = conn.execute(
            """
            SELECT id,version_number,status,summary_json,created_at,activated_at
            FROM ai_profile_versions
            WHERE id=? AND registry_id=? AND user_id=?
            """,
            (
                latest_run["candidate_version_id"],
                registry["id"],
                user_id,
            ),
        ).fetchone()
        if candidate_row:
            candidate = {
                "id": candidate_row["id"],
                "version_number": int(candidate_row["version_number"]),
                "status": candidate_row["status"],
                "summary": _safe_json(candidate_row["summary_json"], {}),
                "created_at": candidate_row["created_at"],
                "activated_at": candidate_row["activated_at"],
            }

    source = None
    if source_row:
        source = {
            "kind": "lightroom_classic",
            "label": "Lightroom Classic",
            "profile_import_id": source_row["id"],
            "profile_name": source_row["profile_name"],
            "catalog_name": source_row["catalog_name"],
            "status": source_row["status"],
            "created_at": source_row["created_at"],
            "updated_at": source_row["updated_at"],
        }

    return {
        "ok": True,
        "format": OVERVIEW_FORMAT,
        "profile_ready": True,
        "active_profile": {
            "registry_id": registry["id"],
            "name": registry["name"],
            "version_id": active["id"],
            "version_number": int(active["version_number"]),
            "activated_at": active["activated_at"],
            "created_at": active["created_at"],
            "recipe_contract_version": active["recipe_contract_version"],
        },
        "learning": {
            "sample_count": int(learning.get("sample_count") or 0),
            "approved_count": int(learning.get("approved_count") or 0),
            "corrected_count": int(learning.get("corrected_count") or 0),
            "acceptance_rate": learning.get("acceptance_rate"),
        },
        "growth": {
            "ready_for_candidate": bool(readiness.get("ready")),
            "remaining_samples": int(readiness.get("remaining_samples") or 0),
            "minimum_samples": int(readiness.get("minimum_samples") or 0),
            "new_samples_since_active": int(readiness.get("new_samples_since_active") or 0),
            "latest_run_status": latest_run.get("status") if latest_run else None,
            "latest_run_progress": int(latest_run.get("progress_percent") or 0) if latest_run else 0,
        },
        "candidate": candidate,
        "source": source,
        "photographer_preferences": onboarding,
    }
