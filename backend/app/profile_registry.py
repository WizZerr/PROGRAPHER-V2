from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REGISTRY_FORMAT = "prographer-ai-profile-registry-v1"
VERSION_FORMAT = "prographer-ai-profile-version-v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_profile_registry_schema(conn: sqlite3.Connection) -> None:
    """
    Additive, idempotent migration.

    No existing table is altered or cleared. Existing users, events, FiveK
    datasets, Vision features, training runs and model artifacts remain intact.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ai_profile_registries (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_profile_import_id TEXT NOT NULL,
            name TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, source_profile_import_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(source_profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ai_profile_versions (
            id TEXT PRIMARY KEY,
            registry_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            source_profile_import_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            profile_format TEXT NOT NULL,
            recipe_contract_version TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            source_runs_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            parent_version_id TEXT,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            UNIQUE(registry_id, version_number),
            UNIQUE(registry_id, source_fingerprint),
            FOREIGN KEY(registry_id) REFERENCES ai_profile_registries(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(source_profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
            FOREIGN KEY(parent_version_id) REFERENCES ai_profile_versions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_ai_profile_registries_user
            ON ai_profile_registries(user_id, created_at);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_profile_registries_one_default
            ON ai_profile_registries(user_id)
            WHERE is_default = 1;

        CREATE INDEX IF NOT EXISTS idx_ai_profile_versions_registry
            ON ai_profile_versions(registry_id, version_number DESC);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_profile_versions_one_active
            ON ai_profile_versions(registry_id)
            WHERE status = 'active';
        """
    )


def _json_load(value: Any, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def _relative_to_data(path: Path, data_dir: Path) -> str:
    path = Path(path).resolve()
    data_dir = Path(data_dir).resolve()
    try:
        return path.relative_to(data_dir).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"Profile artifact must live under PROGRAPHER_DATA_DIR. Got: {path}"
        ) from exc


def resolve_data_path(data_dir: Path, stored_path: str) -> Path:
    candidate = Path(stored_path)
    if candidate.is_absolute():
        return candidate
    return (Path(data_dir) / candidate).resolve()


def _stable_source_fingerprint(manifest: dict[str, Any]) -> str:
    """
    A stable identity for the actual Production Profile decision.

    built_at and filesystem paths are intentionally excluded so pressing
    "rebuild" with the same models/contract does NOT create a fake new version.
    """
    contract = manifest.get("recipe_contract") or {}
    payload = {
        "profile_format": manifest.get("profile_format"),
        "recipe_contract_version": contract.get("version"),
        "selection_basis": manifest.get("selection_basis"),
        "test_used_for_selection": manifest.get("test_used_for_selection"),
        "source_runs": manifest.get("source_runs") or {},
        "parameters": manifest.get("parameters") or {},
        "contract_rules": manifest.get("contract_rules") or {},
        "learning_adaptation": manifest.get("learning_adaptation") or {},
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _row_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


def _version_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["source_runs"] = _json_load(item.pop("source_runs_json", "{}"), {})
    item["summary"] = _json_load(item.pop("summary_json", "{}"), {})
    item["is_active"] = item.get("status") == "active"
    return item


def _registry_summary(conn: sqlite3.Connection, registry_row: sqlite3.Row) -> dict[str, Any]:
    registry = dict(registry_row)
    registry["is_default"] = bool(registry.get("is_default"))

    versions = conn.execute(
        """
        SELECT *
        FROM ai_profile_versions
        WHERE registry_id=? AND user_id=?
        ORDER BY version_number DESC
        """,
        (registry["id"], registry["user_id"]),
    ).fetchall()
    version_items = [_version_dict(row) for row in versions]

    active = next((item for item in version_items if item["status"] == "active"), None)
    latest = version_items[0] if version_items else None

    registry["registry_format"] = REGISTRY_FORMAT
    registry["active_version"] = active
    registry["latest_version"] = latest
    registry["versions"] = version_items
    registry["version_count"] = len(version_items)
    return registry


def get_registry(
    conn: sqlite3.Connection,
    *,
    registry_id: str,
    user_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=? AND user_id=?",
        (registry_id, user_id),
    ).fetchone()
    return _registry_summary(conn, row) if row else None


def get_registry_by_source(
    conn: sqlite3.Connection,
    *,
    source_profile_import_id: str,
    user_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM ai_profile_registries
        WHERE source_profile_import_id=? AND user_id=?
        """,
        (source_profile_import_id, user_id),
    ).fetchone()
    return _registry_summary(conn, row) if row else None


def list_registries(
    conn: sqlite3.Connection,
    *,
    user_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM ai_profile_registries
        WHERE user_id=?
        ORDER BY is_default DESC, created_at ASC
        """,
        (user_id,),
    ).fetchall()
    return [_registry_summary(conn, row) for row in rows]


def get_default_active_profile(
    conn: sqlite3.Connection,
    *,
    user_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM ai_profile_registries
        WHERE user_id=? AND is_default=1
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None

    registry = _registry_summary(conn, row)
    if not registry.get("active_version"):
        return None
    return registry


def _ensure_registry_row(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    source_profile_import_id: str,
    profile_name: str,
) -> sqlite3.Row:
    existing = conn.execute(
        """
        SELECT *
        FROM ai_profile_registries
        WHERE user_id=? AND source_profile_import_id=?
        """,
        (user_id, source_profile_import_id),
    ).fetchone()
    if existing:
        if str(existing["name"]) != str(profile_name):
            conn.execute(
                "UPDATE ai_profile_registries SET name=?, updated_at=? WHERE id=?",
                (profile_name, _utc_now(), existing["id"]),
            )
            existing = conn.execute(
                "SELECT * FROM ai_profile_registries WHERE id=?",
                (existing["id"],),
            ).fetchone()
        return existing

    has_default = conn.execute(
        "SELECT 1 FROM ai_profile_registries WHERE user_id=? AND is_default=1 LIMIT 1",
        (user_id,),
    ).fetchone()

    now = _utc_now()
    registry_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO ai_profile_registries (
            id,user_id,source_profile_import_id,name,is_default,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            registry_id,
            user_id,
            source_profile_import_id,
            profile_name,
            0 if has_default else 1,
            now,
            now,
        ),
    )
    return conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=?",
        (registry_id,),
    ).fetchone()


def register_production_profile_snapshot(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    ai_profiles_dir: Path,
    user_id: str,
    source_profile_import_id: str,
    profile_name: str,
    production_manifest_path: Path,
    production_artifact_path: Path,
) -> dict[str, Any]:
    """
    Register the current Production Profile as an IMMUTABLE version snapshot.

    - Same source decision => deduplicated, no fake version.
    - First version => ACTIVE automatically.
    - Future changed version => READY, never replaces ACTIVE automatically.
    """
    create_profile_registry_schema(conn)

    production_manifest_path = Path(production_manifest_path)
    production_artifact_path = Path(production_artifact_path)
    if not production_manifest_path.exists():
        raise RuntimeError(f"Production manifest not found: {production_manifest_path}")
    if not production_artifact_path.exists():
        raise RuntimeError(f"Production artifact not found: {production_artifact_path}")

    manifest = json.loads(production_manifest_path.read_text(encoding="utf-8"))
    profile_format = str(manifest.get("profile_format") or "")
    recipe_contract_version = str(
        (manifest.get("recipe_contract") or {}).get("version") or ""
    )
    if not profile_format or not recipe_contract_version:
        raise RuntimeError("Production manifest is missing profile/recipe contract version.")

    registry_row = _ensure_registry_row(
        conn,
        user_id=user_id,
        source_profile_import_id=source_profile_import_id,
        profile_name=profile_name,
    )
    registry_id = str(registry_row["id"])
    fingerprint = _stable_source_fingerprint(manifest)

    duplicate = conn.execute(
        """
        SELECT *
        FROM ai_profile_versions
        WHERE registry_id=? AND source_fingerprint=?
        """,
        (registry_id, fingerprint),
    ).fetchone()
    if duplicate:
        # Repair an old/incomplete registry that somehow has versions but no ACTIVE.
        active = conn.execute(
            "SELECT id FROM ai_profile_versions WHERE registry_id=? AND status='active' LIMIT 1",
            (registry_id,),
        ).fetchone()
        if not active:
            now = _utc_now()
            conn.execute(
                "UPDATE ai_profile_versions SET status='active', activated_at=? WHERE id=?",
                (now, duplicate["id"]),
            )
        return _registry_summary(
            conn,
            conn.execute(
                "SELECT * FROM ai_profile_registries WHERE id=?",
                (registry_id,),
            ).fetchone(),
        )

    latest = conn.execute(
        """
        SELECT *
        FROM ai_profile_versions
        WHERE registry_id=?
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (registry_id,),
    ).fetchone()
    next_number = (int(latest["version_number"]) + 1) if latest else 1
    parent_version_id = str(latest["id"]) if latest else None

    active = conn.execute(
        "SELECT id FROM ai_profile_versions WHERE registry_id=? AND status='active' LIMIT 1",
        (registry_id,),
    ).fetchone()
    first_active = active is None

    version_id = str(uuid.uuid4())
    version_root = (
        Path(ai_profiles_dir)
        / user_id
        / source_profile_import_id
        / "registry"
        / "versions"
        / f"v{next_number:04d}"
    )
    version_root.mkdir(parents=True, exist_ok=True)

    artifact_target = version_root / "production_profile.joblib"
    manifest_target = version_root / "production_profile.json"
    shutil.copy2(production_artifact_path, artifact_target)

    now = _utc_now()
    snapshot_manifest = dict(manifest)
    snapshot_manifest["artifact_path"] = _relative_to_data(artifact_target, Path(data_dir))
    snapshot_manifest["registry"] = {
        "registry_format": REGISTRY_FORMAT,
        "version_format": VERSION_FORMAT,
        "registry_id": registry_id,
        "version_id": version_id,
        "version_number": next_number,
        "source_fingerprint": fingerprint,
        "snapshot_created_at": now,
    }
    manifest_target.write_text(
        json.dumps(snapshot_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    status = "active" if first_active else "ready"
    activated_at = now if first_active else None
    source_runs = manifest.get("source_runs") or {}
    summary = manifest.get("summary") or {}

    conn.execute(
        """
        INSERT INTO ai_profile_versions (
            id,registry_id,user_id,source_profile_import_id,version_number,status,
            profile_format,recipe_contract_version,source_fingerprint,
            artifact_path,manifest_path,source_runs_json,summary_json,
            parent_version_id,created_at,activated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            version_id,
            registry_id,
            user_id,
            source_profile_import_id,
            next_number,
            status,
            profile_format,
            recipe_contract_version,
            fingerprint,
            _relative_to_data(artifact_target, Path(data_dir)),
            _relative_to_data(manifest_target, Path(data_dir)),
            json.dumps(source_runs, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
            parent_version_id,
            now,
            activated_at,
        ),
    )
    conn.execute(
        "UPDATE ai_profile_registries SET updated_at=? WHERE id=?",
        (now, registry_id),
    )

    registry_row = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=?",
        (registry_id,),
    ).fetchone()
    return _registry_summary(conn, registry_row)


def activate_version(
    conn: sqlite3.Connection,
    *,
    registry_id: str,
    version_id: str,
    user_id: str,
) -> dict[str, Any]:
    registry = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=? AND user_id=?",
        (registry_id, user_id),
    ).fetchone()
    if not registry:
        raise KeyError("registry_not_found")

    target = conn.execute(
        """
        SELECT *
        FROM ai_profile_versions
        WHERE id=? AND registry_id=? AND user_id=?
        """,
        (version_id, registry_id, user_id),
    ).fetchone()
    if not target:
        raise KeyError("version_not_found")

    if target["status"] == "active":
        return _registry_summary(conn, registry)

    now = _utc_now()
    conn.execute(
        """
        UPDATE ai_profile_versions
        SET status='superseded'
        WHERE registry_id=? AND user_id=? AND status='active'
        """,
        (registry_id, user_id),
    )
    conn.execute(
        """
        UPDATE ai_profile_versions
        SET status='active', activated_at=?
        WHERE id=? AND registry_id=? AND user_id=?
        """,
        (now, version_id, registry_id, user_id),
    )
    conn.execute(
        "UPDATE ai_profile_registries SET updated_at=? WHERE id=?",
        (now, registry_id),
    )

    registry = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=?",
        (registry_id,),
    ).fetchone()
    return _registry_summary(conn, registry)


def set_default_registry(
    conn: sqlite3.Connection,
    *,
    registry_id: str,
    user_id: str,
) -> dict[str, Any]:
    registry = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=? AND user_id=?",
        (registry_id, user_id),
    ).fetchone()
    if not registry:
        raise KeyError("registry_not_found")

    active = conn.execute(
        """
        SELECT id FROM ai_profile_versions
        WHERE registry_id=? AND user_id=? AND status='active'
        LIMIT 1
        """,
        (registry_id, user_id),
    ).fetchone()
    if not active:
        raise RuntimeError("Cannot make a profile default without an ACTIVE version.")

    now = _utc_now()
    conn.execute(
        "UPDATE ai_profile_registries SET is_default=0, updated_at=? WHERE user_id=?",
        (now, user_id),
    )
    conn.execute(
        "UPDATE ai_profile_registries SET is_default=1, updated_at=? WHERE id=? AND user_id=?",
        (now, registry_id, user_id),
    )

    registry = conn.execute(
        "SELECT * FROM ai_profile_registries WHERE id=?",
        (registry_id,),
    ).fetchone()
    return _registry_summary(conn, registry)


def resolve_active_artifact(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    user_id: str,
) -> tuple[Path, dict[str, Any]]:
    """
    Single resolver for Stage 3 inference.

    It intentionally resolves ONLY the user's DEFAULT registry and its ACTIVE
    immutable version. A READY candidate can never leak into production.
    """
    registry = get_default_active_profile(conn, user_id=user_id)
    if not registry:
        raise RuntimeError("No default ACTIVE AI Profile is available.")

    version = registry["active_version"]
    artifact = resolve_data_path(Path(data_dir), str(version["artifact_path"]))
    if not artifact.exists():
        raise RuntimeError(f"ACTIVE AI Profile artifact is missing: {artifact}")
    return artifact, registry
