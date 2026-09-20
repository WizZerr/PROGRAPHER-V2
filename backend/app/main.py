from __future__ import annotations

import colorsys
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
import secrets
import hmac
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import psutil
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, ImageStat, ImageEnhance, ImageFilter
from .ai import brain_status, get_brain, BrainUnavailableError
from .lightroom import scan_catalogs, analyze_catalog, catalog_roots, LightroomCatalogError, build_training_dataset, audit_training_dataset
from .profile_ai import (
    build_vision_features,
    train_context_model,
    evaluate_context_model,
    load_vision_image,
    extract_training_metadata,
)
from .recipe_v2 import build_recipe_v2_dataset, train_context_model_v2
from .recipes import recipe_contract_public, canonicalize_recipe
from .production_profile import build_production_profile_v1
from .profile_registry import (
    create_profile_registry_schema,
    register_production_profile_snapshot,
    list_registries,
    get_registry,
    get_registry_by_source,
    get_default_active_profile,
    activate_version,
    set_default_registry,
    resolve_active_artifact,
)
from .inference import (
    VISION_PREPROCESSING_CONTRACT,
    create_inference_schema,
    brain_matches_production_contract,
    latest_prediction_for_photo,
    current_prediction_map,
    predict_photo_with_active_registry,
    event_prediction_coverage,
    create_event_inference_job,
    update_event_inference_job,
    latest_event_inference_job,
    active_event_inference_job,
)
from .darkroom import (
    DARKROOM_PREVIEW_FORMAT,
    create_production_darkroom_schema,
    infer_process_family,
    latest_ai_preview_render,
    render_production_recipe_preview,
    save_prediction_preview_render,
)
from .learning import (
    LEARNING_SAMPLE_FORMAT,
    create_learning_schema,
    latest_learning_for_photo,
    save_learning_decision,
    set_learning_final_render,
    learning_summary,
)
from .retraining import (
    RETRAINING_FORMAT,
    MIN_TOTAL_SAMPLES,
    create_retraining_schema,
    retraining_readiness,
    latest_retraining_run,
    active_retraining_run,
    create_retraining_run,
    update_retraining_run,
    build_adaptive_candidate,
)
from .event_export import (
    EXPORT_FORMAT,
    create_export_schema,
    event_completion_status,
    latest_event_export,
    build_event_xmp_export,
    build_lightroom_xmp,
    dominant_lightroom_source_metadata,
)
from .product_overview import (
    OVERVIEW_FORMAT,
    photographer_profile_overview,
)

# RAW is optional in V0.
try:
    import rawpy  # type: ignore
    RAW_ENABLED = True
except Exception:
    rawpy = None
    RAW_ENABLED = False

try:
    import exifread  # type: ignore
    EXIFREAD_ENABLED = True
except Exception:
    exifread = None
    EXIFREAD_ENABLED = False

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def resolve_data_dir() -> Path:
    configured = os.getenv("PROGRAPHER_DATA_DIR", "./data").strip()
    path = Path(configured)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

DATA_DIR = resolve_data_dir()
EVENTS_DIR = DATA_DIR / "events"
STYLE_DIR = DATA_DIR / "style"
AI_PROFILES_DIR = DATA_DIR / "ai_profiles"
DB_PATH = DATA_DIR / "prographer.db"

EVENTS_DIR.mkdir(parents=True, exist_ok=True)
STYLE_DIR.mkdir(parents=True, exist_ok=True)
AI_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv("PROGRAPHER_PUBLIC_BASE_URL", "").strip().rstrip("/")
REQUIRE_TOKEN = os.getenv("PROGRAPHER_REQUIRE_TOKEN", "false").lower() == "true"
ACCESS_TOKEN = os.getenv("PROGRAPHER_TOKEN", "change-me").strip()

allowed_origins = [
    x.strip()
    for x in os.getenv(
        "PROGRAPHER_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://prographer.proride.co.il",
    ).split(",")
    if x.strip()
]

app = FastAPI(
    title="ProGrapher Local Engine",
    version="2.1.3",
    description="המנוע המקומי של ProGrapher",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def allow_private_network_access(request: Request, call_next):
    """
    Chrome/Edge may preflight requests from the HTTPS Hostinger frontend
    to the local engine on 127.0.0.1. This header allows that private/local
    network request when the normal CORS origin is already allowed.
    """
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network") == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                studio_name TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_onboarding (
                user_id TEXT PRIMARY KEY,
                specialties_json TEXT DEFAULT '[]',
                editor_software TEXT DEFAULT '',
                style_words_json TEXT DEFAULT '[]',
                priorities_json TEXT DEFAULT '[]',
                notes TEXT DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT,
                style_note TEXT,
                status TEXT NOT NULL DEFAULT 'טיוטה',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                preview_path TEXT,
                edited_path TEXT,
                file_size INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                width INTEGER,
                height INTEGER,
                status TEXT NOT NULL DEFAULT 'הועלה',
                confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS style_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                description TEXT DEFAULT '',
                calibration_score REAL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS style_pairs (
                id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                edited_name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                edited_path TEXT NOT NULL,
                scene_label TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                ai_recipe_json TEXT,
                photographer_recipe_json TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS style_learning_archive (
                id TEXT PRIMARY KEY,
                source_event_id TEXT,
                source_feedback_id TEXT,
                verdict TEXT NOT NULL,
                ai_recipe_json TEXT,
                photographer_recipe_json TEXT,
                created_at TEXT NOT NULL,
                archived_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lightroom_profile_imports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                profile_name TEXT NOT NULL,
                catalog_path TEXT NOT NULL,
                catalog_name TEXT NOT NULL,
                selected_collections_json TEXT NOT NULL DEFAULT '[]',
                analysis_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'catalog_analyzed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lightroom_dataset_builds (
                id TEXT PRIMARY KEY,
                profile_import_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                manifest_json TEXT NOT NULL DEFAULT '{}',
                output_dir TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lightroom_dataset_audits (
                id TEXT PRIMARY KEY,
                profile_import_id TEXT NOT NULL,
                dataset_build_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL DEFAULT '{}',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
                FOREIGN KEY(dataset_build_id) REFERENCES lightroom_dataset_builds(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lightroom_vision_jobs (
                id TEXT PRIMARY KEY,
                profile_import_id TEXT NOT NULL,
                dataset_build_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                manifest_json TEXT NOT NULL DEFAULT '{}',
                output_dir TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
                FOREIGN KEY(dataset_build_id) REFERENCES lightroom_dataset_builds(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lightroom_training_runs (
                id TEXT PRIMARY KEY,
                profile_import_id TEXT NOT NULL,
                vision_job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                model_path TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
                FOREIGN KEY(vision_job_id) REFERENCES lightroom_vision_jobs(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lightroom_training_v2_runs (
                id TEXT PRIMARY KEY,
                profile_import_id TEXT NOT NULL,
                vision_job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                model_path TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_import_id) REFERENCES lightroom_profile_imports(id) ON DELETE CASCADE,
                FOREIGN KEY(vision_job_id) REFERENCES lightroom_vision_jobs(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            INSERT OR IGNORE INTO style_profile (id, description, calibration_score, updated_at)
            VALUES (1, '', 0, datetime('now'));
            """
        )

        # V1.5.0 — immutable AI Profile Registry + ACTIVE version pointer.
        # Additive migration only: no existing data is deleted or rewritten.
        create_profile_registry_schema(conn)

        # V1.6.0 — Active Profile inference predictions + resumable event jobs.
        # Additive only. Existing Events / FiveK / Vision / Training stay untouched.
        create_inference_schema(conn)

        # V1.7.0 — Production Prediction -> Darkroom preview bridge.
        # Additive only; legacy render/feedback rows remain untouched.
        create_production_darkroom_schema(conn)

        # V1.8.0 — canonical Production learning capture.
        # Separate from legacy feedback / Style DNA; additive only.
        create_learning_schema(conn)

        # V1.9.0 — adaptive retraining jobs + candidate Profile versions.
        create_retraining_schema(conn)

        # V2.0.0 — event completion + Lightroom XMP export history.
        create_export_schema(conn)

        # V0.3 migration: metadata JSON for existing and future photos.
        photo_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(photos)").fetchall()
        }
        if "metadata_json" not in photo_columns:
            conn.execute("ALTER TABLE photos ADD COLUMN metadata_json TEXT")
        if "metadata_updated_at" not in photo_columns:
            conn.execute("ALTER TABLE photos ADD COLUMN metadata_updated_at TEXT")

        event_columns = {row["name"] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
        if "user_id" not in event_columns:
            conn.execute("ALTER TABLE events ADD COLUMN user_id TEXT")

        archive_columns = {row["name"] for row in conn.execute("PRAGMA table_info(style_learning_archive)").fetchall()}
        if "user_id" not in archive_columns:
            conn.execute("ALTER TABLE style_learning_archive ADD COLUMN user_id TEXT")

        pair_columns = {row["name"] for row in conn.execute("PRAGMA table_info(style_pairs)").fetchall()}
        if "user_id" not in pair_columns:
            conn.execute("ALTER TABLE style_pairs ADD COLUMN user_id TEXT")

        # V1.2 temporarily assigned every pre-auth event to the first registered
        # account. V1.2.1 fixes that model: pre-existing research data remains
        # unassigned (user_id NULL) unless explicitly migrated later.
        first_user = conn.execute(
            "SELECT id, created_at FROM users ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if first_user:
            conn.execute(
                """
                UPDATE events
                SET user_id = NULL
                WHERE user_id = ?
                  AND created_at < ?
                """,
                (first_user["id"], first_user["created_at"]),
            )
            conn.execute(
                """
                UPDATE style_learning_archive
                SET user_id = NULL
                WHERE user_id = ?
                  AND created_at < ?
                """,
                (first_user["id"], first_user["created_at"]),
            )
            conn.execute(
                """
                UPDATE style_pairs
                SET user_id = NULL
                WHERE user_id = ?
                  AND created_at < ?
                """,
                (first_user["id"], first_user["created_at"]),
            )

        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS photo_analyses (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                recipe_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photo_renders (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                recipe_json TEXT NOT NULL,
                rendered_path TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photo_brain_vision (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                device TEXT NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                semantics_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );
            '''
        )

init_db()

class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    event_type: str = "אחר"
    event_date: Optional[str] = None
    style_note: Optional[str] = None

class EventUpdate(BaseModel):
    name: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    style_note: Optional[str] = None
    status: Optional[str] = None

class StyleProfileUpdate(BaseModel):
    description: str = ""
    calibration_score: float = Field(default=0, ge=0, le=100)

class FeedbackCreate(BaseModel):
    verdict: str
    ai_recipe: Optional[dict] = None
    photographer_recipe: Optional[dict] = None
    note: Optional[str] = None


class CustomRenderRequest(BaseModel):
    recipe: dict
    commit: bool = False


class ProductionDarkroomPreviewRequest(BaseModel):
    recipe: dict


class ProductionLearningDecisionRequest(BaseModel):
    verdict: str
    photographer_recipe: Optional[dict] = None
    note: Optional[str] = None


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    studio_name: str = Field(default="", max_length=160)


class LoginRequest(BaseModel):
    email: str
    password: str


class OnboardingUpdate(BaseModel):
    specialties: list[str] = []
    editor_software: str = ""
    style_words: list[str] = []
    priorities: list[str] = []
    notes: str = ""
    completed: bool = True


class LightroomCatalogAnalyzeRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4000)

class LightroomProfileImportCreate(BaseModel):
    profile_name: str = Field(min_length=1, max_length=160)
    catalog_path: str = Field(min_length=1, max_length=4000)
    selected_collections: list[str] = []
    analysis: dict = {}


def _password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_raw, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256": return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations_raw))
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except Exception:
        return False


def _session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _user_onboarding(conn, user_id: str) -> dict:
    row = conn.execute("SELECT * FROM user_onboarding WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return {"specialties": [], "editor_software": "", "style_words": [], "priorities": [], "notes": "", "completed": False}
    return {
        "specialties": json.loads(row["specialties_json"] or "[]"),
        "editor_software": row["editor_software"] or "",
        "style_words": json.loads(row["style_words_json"] or "[]"),
        "priorities": json.loads(row["priorities_json"] or "[]"),
        "notes": row["notes"] or "",
        "completed": bool(row["completed"]),
    }


def _public_user(row, onboarding_completed: bool = False) -> dict:
    return {
        "id": row["id"], "email": row["email"], "display_name": row["display_name"],
        "studio_name": row["studio_name"] or "", "onboarding_completed": bool(onboarding_completed),
        "created_at": row["created_at"],
    }


def require_access(x_prographer_token: Optional[str] = Header(default=None)) -> None:
    if not REQUIRE_TOKEN:
        return
    if not x_prographer_token or x_prographer_token != ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="גישה לא מורשית")


def require_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_prographer_token: Optional[str] = Header(default=None),
) -> dict:
    require_access(x_prographer_token)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="נדרשת התחברות")
    token = authorization.split(" ", 1)[1].strip()
    token_hash = _session_token_hash(token)
    now = utc_now()
    with db() as conn:
        row = conn.execute("""
            SELECT u.*, s.expires_at FROM user_sessions s
            INNER JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?
        """, (token_hash,)).fetchone()
        if not row or str(row["expires_at"]) <= now:
            if row: conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
            raise HTTPException(status_code=401, detail="פג תוקף ההתחברות")
        user_id = row["id"]
        event_id = request.path_params.get("event_id")
        if event_id:
            owner = conn.execute("SELECT user_id FROM events WHERE id = ?", (event_id,)).fetchone()
            if not owner or owner["user_id"] != user_id: raise HTTPException(status_code=404, detail="האירוע לא נמצא")
        photo_id = request.path_params.get("photo_id")
        if photo_id:
            owner = conn.execute("""SELECT e.user_id FROM photos p INNER JOIN events e ON e.id = p.event_id WHERE p.id = ?""", (photo_id,)).fetchone()
            if not owner or owner["user_id"] != user_id: raise HTTPException(status_code=404, detail="התמונה לא נמצאה")
        onboarding = _user_onboarding(conn, user_id)
        user = _public_user(row, onboarding["completed"])
    request.state.user = user
    return user


def owner_user_id_for_photo(photo_id: str) -> Optional[str]:
    with db() as conn:
        row = conn.execute("""SELECT e.user_id FROM photos p INNER JOIN events e ON e.id = p.event_id WHERE p.id = ?""", (photo_id,)).fetchone()
    return row["user_id"] if row else None

def clean_filename(name: str) -> str:
    name = Path(name).name.strip()
    name = re.sub(r"[^A-Za-z0-9א-ת._\- ()\[\]]+", "_", name)
    return (name or "photo")[:180]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def url_for_media(request: Request, relative_path: str) -> str:
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/api/media/{relative_path}"
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/media/{relative_path}"

def event_dirs(event_id: str) -> dict[str, Path]:
    root = EVENTS_DIR / event_id
    paths = {
        "root": root,
        "originals": root / "originals",
        "previews": root / "previews",
        "edited": root / "edited",
        "metadata": root / "metadata",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths

SUPPORTED_RASTER = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
SUPPORTED_RAW = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef"
}

def require_production_raw_photo(photo_row) -> None:
    name = str(photo_row["original_name"] if isinstance(photo_row, sqlite3.Row) else photo_row.get("original_name") or "")
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_RAW:
        raise HTTPException(
            415,
            "ProGrapher V1 עורך כרגע RAW בלבד. "
            "JPG/PNG/WEBP אינם נכנסים למסלול של פרופיל שאומן מ-Lightroom RAW. "
            "העלה CR2/CR3/NEF/ARW/DNG/ORF/RW2/RAF/PEF.",
        )

def create_preview(source: Path, destination: Path) -> tuple[bool, Optional[int], Optional[int], str]:
    suffix = source.suffix.lower()
    try:
        if suffix in SUPPORTED_RASTER:
            with Image.open(source) as img:
                img = ImageOps.exif_transpose(img)
                img = img.convert("RGB")
                width, height = img.size
                img.thumbnail((2200, 2200))
                destination.parent.mkdir(parents=True, exist_ok=True)
                img.save(destination, "JPEG", quality=88, optimize=True)
                return True, width, height, "תצוגה מקדימה מוכנה"

        if suffix in SUPPORTED_RAW:
            if not RAW_ENABLED:
                return False, None, None, "RAW הועלה - נדרש rawpy ליצירת תצוגה מקדימה"

            with rawpy.imread(str(source)) as raw:
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    no_auto_bright=True,
                    half_size=True,
                    output_bps=8,
                )
            img = Image.fromarray(rgb)
            width, height = img.size
            img.thumbnail((2200, 2200))
            destination.parent.mkdir(parents=True, exist_ok=True)
            img.save(destination, "JPEG", quality=88, optimize=True)
            return True, width, height, "תצוגה מקדימה RAW מוכנה"

        return False, None, None, "סוג קובץ נשמר ללא תצוגה מקדימה"
    except Exception as exc:
        return False, None, None, f"שגיאה ביצירת תצוגה מקדימה: {exc.__class__.__name__}"


def _tag_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _first_tag(tags: dict, *names: str) -> Optional[str]:
    for name in names:
        if name in tags:
            value = _tag_text(tags.get(name))
            if value:
                return value
    return None

def _format_aperture(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip()
    if text.lower().startswith("f/"):
        return text
    return f"f/{text}"

def extract_photo_metadata(source: Path, width: Optional[int] = None, height: Optional[int] = None) -> dict:
    suffix = source.suffix.lower()
    metadata = {
        "file_type": suffix.lstrip(".").upper() or "UNKNOWN",
        "is_raw": suffix in SUPPORTED_RAW,
        "camera_make": None,
        "camera_model": None,
        "lens": None,
        "iso": None,
        "aperture": None,
        "shutter_speed": None,
        "focal_length": None,
        "date_taken": None,
        "width": width,
        "height": height,
        "metadata_source": "basic",
    }

    # exifread handles DNG and many camera RAW formats, so prefer it.
    if EXIFREAD_ENABLED:
        try:
            with source.open("rb") as handle:
                tags = exifread.process_file(
                    handle,
                    details=False,
                    strict=False,
                    stop_tag="UNDEF",
                )

            metadata.update(
                {
                    "camera_make": _first_tag(tags, "Image Make"),
                    "camera_model": _first_tag(tags, "Image Model"),
                    "lens": _first_tag(
                        tags,
                        "EXIF LensModel",
                        "Image LensModel",
                        "MakerNote LensType",
                    ),
                    "iso": _first_tag(
                        tags,
                        "EXIF ISOSpeedRatings",
                        "EXIF PhotographicSensitivity",
                    ),
                    "aperture": _format_aperture(
                        _first_tag(tags, "EXIF FNumber", "EXIF ApertureValue")
                    ),
                    "shutter_speed": _first_tag(
                        tags,
                        "EXIF ExposureTime",
                        "EXIF ShutterSpeedValue",
                    ),
                    "focal_length": _first_tag(tags, "EXIF FocalLength"),
                    "date_taken": _first_tag(
                        tags,
                        "EXIF DateTimeOriginal",
                        "EXIF DateTimeDigitized",
                        "Image DateTime",
                    ),
                    "metadata_source": "exifread",
                }
            )
        except Exception:
            pass

    # Pillow fallback for ordinary images.
    if metadata["metadata_source"] == "basic" and suffix in SUPPORTED_RASTER:
        try:
            from PIL.ExifTags import TAGS
            with Image.open(source) as img:
                if metadata["width"] is None or metadata["height"] is None:
                    metadata["width"], metadata["height"] = img.size
                raw_exif = img.getexif()
                friendly = {
                    TAGS.get(k, str(k)): v
                    for k, v in raw_exif.items()
                }
                metadata.update(
                    {
                        "camera_make": _tag_text(friendly.get("Make")),
                        "camera_model": _tag_text(friendly.get("Model")),
                        "lens": _tag_text(friendly.get("LensModel")),
                        "iso": _tag_text(
                            friendly.get("ISOSpeedRatings")
                            or friendly.get("PhotographicSensitivity")
                        ),
                        "aperture": _format_aperture(_tag_text(friendly.get("FNumber"))),
                        "shutter_speed": _tag_text(friendly.get("ExposureTime")),
                        "focal_length": _tag_text(friendly.get("FocalLength")),
                        "date_taken": _tag_text(
                            friendly.get("DateTimeOriginal")
                            or friendly.get("DateTimeDigitized")
                            or friendly.get("DateTime")
                        ),
                        "metadata_source": "pillow",
                    }
                )
        except Exception:
            pass

    if metadata["focal_length"] and "mm" not in metadata["focal_length"].lower():
        metadata["focal_length"] = f'{metadata["focal_length"]} mm'

    return metadata

def save_metadata_sidecar(event_id: str, photo_id: str, metadata: dict) -> None:
    dirs = event_dirs(event_id)
    sidecar = dirs["metadata"] / f"{photo_id}.json"
    sidecar.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def ensure_row_metadata(row: sqlite3.Row) -> dict:
    item = dict(row)
    existing = item.get("metadata_json")
    if existing:
        try:
            return json.loads(existing)
        except Exception:
            pass

    source = DATA_DIR / item["original_path"]
    metadata = extract_photo_metadata(
        source,
        width=item.get("width"),
        height=item.get("height"),
    )

    with db() as conn:
        conn.execute(
            """
            UPDATE photos
            SET metadata_json = ?, metadata_updated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(metadata, ensure_ascii=False),
                utc_now(),
                utc_now(),
                item["id"],
            ),
        )
    save_metadata_sidecar(item["event_id"], item["id"], metadata)
    return metadata

def row_to_photo(request: Request, row: sqlite3.Row, include_metadata: bool = True) -> dict:
    item = dict(row)
    if item.get("preview_path"):
        item["preview_url"] = url_for_media(request, item["preview_path"])
    else:
        item["preview_url"] = None

    if item.get("edited_path"):
        item["edited_url"] = url_for_media(request, item["edited_path"])
    else:
        item["edited_url"] = None

    item["extension"] = Path(item.get("original_name") or "").suffix.lstrip(".").upper()
    item["is_raw"] = Path(item.get("original_name") or "").suffix.lower() in SUPPORTED_RAW

    if include_metadata:
        item["metadata"] = ensure_row_metadata(row)

    return item

def system_gpu_info() -> dict:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            first = result.stdout.strip().splitlines()[0]
            name, total, used, util, temp = [x.strip() for x in first.split(",")]
            return {
                "available": True,
                "name": name,
                "memory_total_mb": int(total),
                "memory_used_mb": int(used),
                "utilization_percent": int(util),
                "temperature_c": int(temp),
            }
    except Exception:
        pass
    return {"available": False}

@app.get("/")
def root():
    return {
        "service": "ProGrapher Local Engine",
        "version": "2.1.3",
        "docs": "/docs",
        "health": "/api/health",
    }

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "ProGrapher Local Engine",
        "version": "2.1.3",
        "raw_support": RAW_ENABLED,
        "exif_support": EXIFREAD_ENABLED,
        "data_dir": str(DATA_DIR),
        "browser_local_mode": True,
        "allowed_origins": allowed_origins,
        "time": utc_now(),
    }

@app.get("/api/auth/bootstrap")
def auth_bootstrap():
    with db() as conn:
        user_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {"ok": True, "has_users": user_count > 0, "registration_open": True}

@app.post("/api/auth/register")
def auth_register(payload: RegisterRequest):
    email = payload.email.strip().lower(); display_name = payload.display_name.strip(); studio_name = payload.studio_name.strip()
    if "@" not in email: raise HTTPException(400, "כתובת האימייל אינה תקינה")
    now=utc_now(); user_id=str(uuid.uuid4())
    with db() as conn:
        if conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone(): raise HTTPException(409, "כבר קיים משתמש עם האימייל הזה")
        conn.execute("""INSERT INTO users (id,email,password_hash,display_name,studio_name,created_at,updated_at) VALUES (?,?,?,?,?,?,?)""", (user_id,email,_password_hash(payload.password),display_name,studio_name,now,now))
        conn.execute("""INSERT INTO user_onboarding (user_id,specialties_json,editor_software,style_words_json,priorities_json,notes,completed,updated_at) VALUES (?, '[]', '', '[]', '[]', '', 0, ?)""", (user_id,now))
        token=secrets.token_urlsafe(40); expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(timespec="seconds")
        conn.execute("INSERT INTO user_sessions (id,user_id,token_hash,created_at,expires_at) VALUES (?,?,?,?,?)", (str(uuid.uuid4()),user_id,_session_token_hash(token),now,expires))
        row=conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"ok": True, "token": token, "user": _public_user(row, False)}

@app.post("/api/auth/login")
def auth_login(payload: LoginRequest):
    with db() as conn:
        row=conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (payload.email.strip().lower(),)).fetchone()
        if not row or not _verify_password(payload.password,row["password_hash"]): raise HTTPException(401,"אימייל או סיסמה שגויים")
        onboarding=_user_onboarding(conn,row["id"]); token=secrets.token_urlsafe(40); now=utc_now(); expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(timespec="seconds")
        conn.execute("INSERT INTO user_sessions (id,user_id,token_hash,created_at,expires_at) VALUES (?,?,?,?,?)", (str(uuid.uuid4()),row["id"],_session_token_hash(token),now,expires))
    return {"ok": True, "token": token, "user": _public_user(row,onboarding["completed"])}

@app.get("/api/auth/me")
def auth_me(user=Depends(require_user)):
    with db() as conn: onboarding=_user_onboarding(conn,user["id"])
    return {"ok": True, "user": user, "onboarding": onboarding}

@app.post("/api/auth/logout")
def auth_logout(authorization: Optional[str]=Header(default=None), user=Depends(require_user)):
    if authorization and authorization.lower().startswith("bearer "):
        with db() as conn: conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (_session_token_hash(authorization.split(" ",1)[1].strip()),))
    return {"ok": True}

@app.get("/api/auth/onboarding")
def get_onboarding(user=Depends(require_user)):
    with db() as conn: onboarding=_user_onboarding(conn,user["id"])
    return {"ok": True, "onboarding": onboarding}

@app.put("/api/auth/onboarding")
def update_onboarding(payload: OnboardingUpdate, user=Depends(require_user)):
    now=utc_now()
    with db() as conn:
        conn.execute("""INSERT INTO user_onboarding (user_id,specialties_json,editor_software,style_words_json,priorities_json,notes,completed,updated_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET specialties_json=excluded.specialties_json,editor_software=excluded.editor_software,style_words_json=excluded.style_words_json,priorities_json=excluded.priorities_json,notes=excluded.notes,completed=excluded.completed,updated_at=excluded.updated_at""", (user["id"],json.dumps(payload.specialties,ensure_ascii=False),payload.editor_software.strip(),json.dumps(payload.style_words,ensure_ascii=False),json.dumps(payload.priorities,ensure_ascii=False),payload.notes.strip(),1 if payload.completed else 0,now))
        onboarding=_user_onboarding(conn,user["id"])
    return {"ok": True, "onboarding": onboarding}



DATASET_STAGE_HE = {
    "queued": "מתחילים להכין את הפרופיל",
    "safe_catalog_copy": "מכינים עותק בטוח של קטלוג Lightroom",
    "reading_lightroom": "קוראים את מבנה העריכות",
    "mapping_pairs": "מחברים תמונות לעריכות שלהן",
    "matching_files": "מאמתים את קבצי המקור במחשב",
    "extracting_recipes": "קוראים את החלטות העריכה של Lightroom",
    "validating_pairs": "מאמתים התאמות אחת־לאחת",
    "writing_dataset": "מכינים את חומר הלמידה",
    "completed": "Dataset מוכן",
    "failed": "בניית ה־Dataset נעצרה",
}


def _dataset_build_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["details"] = json.loads(item.pop("details_json") or "{}")
    item["manifest"] = json.loads(item.pop("manifest_json") or "{}")
    item["stage_he"] = DATASET_STAGE_HE.get(item.get("stage"), item.get("stage") or "")
    return item


def _dataset_build_for_profile(conn: sqlite3.Connection, profile_import_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
        (profile_import_id, user_id),
    ).fetchone()
    return _dataset_build_dict(row) if row else None


AUDIT_STAGE_HE = {
    "queued": "מתחילים בדיקת תקינות",
    "reading_dataset": "קוראים את קבצי ה-Dataset",
    "checking_pairs": "מאמתים התאמות RAW לעריכות Lightroom",
    "checking_files": "בודקים את קבצי המקור במחשב",
    "checking_recipes": "מאמתים את Recipes של Lightroom",
    "checking_splits": "בודקים שאין דליפה בין Train / Validation / Test",
    "sampling": "מבצעים בדיקה מדגמית",
    "completed": "בדיקת התקינות הושלמה",
    "failed": "בדיקת התקינות נעצרה",
}


def _dataset_audit_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["result"] = json.loads(item.pop("result_json") or "{}")
    item["stage_he"] = AUDIT_STAGE_HE.get(item.get("stage"), item.get("stage") or "")
    return item


def _dataset_audit_for_profile(conn: sqlite3.Connection, profile_import_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM lightroom_dataset_audits WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
        (profile_import_id, user_id),
    ).fetchone()
    return _dataset_audit_dict(row) if row else None


def _update_dataset_audit(audit_id: str, *, status=None, stage=None, progress=None, result=None, error=None):
    fields, values = [], []
    if status is not None: fields += ["status=?"]; values += [status]
    if stage is not None: fields += ["stage=?"]; values += [stage]
    if progress is not None: fields += ["progress_percent=?"]; values += [int(progress)]
    if result is not None: fields += ["result_json=?"]; values += [json.dumps(result, ensure_ascii=False)]
    if error is not None: fields += ["error=?"]; values += [str(error)]
    fields += ["updated_at=?"]; values += [utc_now()]
    values.append(audit_id)
    with db() as conn:
        conn.execute(f"UPDATE lightroom_dataset_audits SET {', '.join(fields)} WHERE id=?", values)


def _run_lightroom_dataset_audit(audit_id: str, profile_import_id: str, dataset_build_id: str, user_id: str):
    try:
        # Immediate heartbeat: if the thread is alive, the UI must never sit at
        # the initial queued 1% state for minutes.
        _update_dataset_audit(
            audit_id,
            status="building",
            stage="starting",
            progress=2,
            error="",
        )

        with db() as conn:
            build = conn.execute(
                "SELECT * FROM lightroom_dataset_builds WHERE id=? AND profile_import_id=? AND user_id=?",
                (dataset_build_id, profile_import_id, user_id),
            ).fetchone()
        if not build or build["status"] != "completed":
            raise RuntimeError("Dataset מלא נדרש לפני בדיקת התקינות")
        output_dir = Path(build["output_dir"] or "")
        manifest = json.loads(build["manifest_json"] or "{}")

        def progress_cb(stage: str, pct: int, detail: dict):
            _update_dataset_audit(audit_id, status="building", stage=stage, progress=pct)

        result = audit_training_dataset(output_dir, manifest=manifest, progress=progress_cb)
        _update_dataset_audit(
            audit_id,
            status="completed",
            stage="completed",
            progress=100,
            result=result,
            error="" if result.get("passed") else "Dataset Integrity Audit לא עבר את כל הבדיקות הקריטיות.",
        )
    except Exception as exc:
        _update_dataset_audit(
            audit_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
        )


def _start_lightroom_dataset_audit(profile_import_id: str, dataset_build_id: str, user_id: str) -> dict:
    now = utc_now()
    audit_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO lightroom_dataset_audits (id,profile_import_id,dataset_build_id,user_id,status,stage,progress_percent,result_json,error,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (audit_id, profile_import_id, dataset_build_id, user_id, "queued", "queued", 1, "{}", "", now, now),
        )
        row = conn.execute("SELECT * FROM lightroom_dataset_audits WHERE id=?", (audit_id,)).fetchone()
    thread = threading.Thread(
        target=_run_lightroom_dataset_audit,
        args=(audit_id, profile_import_id, dataset_build_id, user_id),
        daemon=True,
        name=f"prographer-audit-{audit_id[:8]}",
    )
    thread.start()
    return _dataset_audit_dict(row)


def _update_dataset_build(build_id: str, *, status=None, stage=None, progress=None, details=None, manifest=None, output_dir=None, error=None):
    fields, values = [], []
    if status is not None: fields += ["status=?"]; values += [status]
    if stage is not None: fields += ["stage=?"]; values += [stage]
    if progress is not None: fields += ["progress_percent=?"]; values += [int(progress)]
    if details is not None: fields += ["details_json=?"]; values += [json.dumps(details, ensure_ascii=False)]
    if manifest is not None: fields += ["manifest_json=?"]; values += [json.dumps(manifest, ensure_ascii=False)]
    if output_dir is not None: fields += ["output_dir=?"]; values += [str(output_dir)]
    if error is not None: fields += ["error=?"]; values += [str(error)]
    fields += ["updated_at=?"]; values += [utc_now()]
    values.append(build_id)
    with db() as conn:
        conn.execute(f"UPDATE lightroom_dataset_builds SET {', '.join(fields)} WHERE id=?", values)


def _run_lightroom_dataset_build(build_id: str, profile_import_id: str, user_id: str):
    try:
        with db() as conn:
            profile = conn.execute(
                "SELECT * FROM lightroom_profile_imports WHERE id=? AND user_id=?",
                (profile_import_id, user_id),
            ).fetchone()
            if not profile:
                raise RuntimeError("פרופיל Lightroom לא נמצא")
            analysis = json.loads(profile["analysis_json"] or "{}")
            selected = json.loads(profile["selected_collections_json"] or "[]")

        groups = analysis.get("training_groups") or []
        selected_group = None
        if selected:
            selected_group = next((g for g in groups if str(g.get("id")) == str(selected[0])), None)
        if selected_group is None and not groups:
            selected_group = {"id": "whole-catalog", "name": "Whole Catalog", "display_name": "כל הקטלוג", "kind": "whole_catalog"}
        if selected_group is None:
            raise RuntimeError("לא הצלחנו לזהות את סגנון העריכה שנבחר")

        output_dir = AI_PROFILES_DIR / user_id / profile_import_id / "dataset"
        output_dir.mkdir(parents=True, exist_ok=True)
        _update_dataset_build(build_id, status="building", stage="queued", progress=2, output_dir=output_dir, details={"style": selected_group})

        last_details = {"style": selected_group}
        def progress_cb(stage: str, pct: int, detail: dict):
            nonlocal last_details
            last_details = {**last_details, **(detail or {})}
            _update_dataset_build(build_id, status="building", stage=stage, progress=pct, details=last_details)

        manifest = build_training_dataset(
            profile["catalog_path"],
            selected_group,
            output_dir,
            progress=progress_cb,
        )
        _update_dataset_build(
            build_id,
            status="completed",
            stage="completed",
            progress=100,
            details={**last_details, **manifest},
            manifest=manifest,
        )
        with db() as conn:
            conn.execute(
                "UPDATE lightroom_profile_imports SET status='dataset_ready', updated_at=? WHERE id=? AND user_id=?",
                (utc_now(), profile_import_id, user_id),
            )
        _start_lightroom_dataset_audit(profile_import_id, build_id, user_id)
    except Exception as exc:
        _update_dataset_build(
            build_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
            details={"error": str(exc)},
        )
        with db() as conn:
            conn.execute(
                "UPDATE lightroom_profile_imports SET status='dataset_failed', updated_at=? WHERE id=? AND user_id=?",
                (utc_now(), profile_import_id, user_id),
            )


def _start_lightroom_dataset_build(profile_import_id: str, user_id: str) -> dict:
    build_id = str(uuid.uuid4())
    now = utc_now()
    with db() as conn:
        conn.execute(
            "INSERT INTO lightroom_dataset_builds (id,profile_import_id,user_id,status,stage,progress_percent,details_json,manifest_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (build_id, profile_import_id, user_id, "queued", "queued", 1, "{}", "{}", now, now),
        )
        row = conn.execute("SELECT * FROM lightroom_dataset_builds WHERE id=?", (build_id,)).fetchone()
    thread = threading.Thread(
        target=_run_lightroom_dataset_build,
        args=(build_id, profile_import_id, user_id),
        daemon=True,
        name=f"prographer-dataset-{build_id[:8]}",
    )
    thread.start()
    return _dataset_build_dict(row)



VISION_STAGE_HE = {
    "queued": "ממתינים לניתוח Vision",
    "warming_vision": "טוענים את מודל ה-Vision המקומי",
    "vision_processing": "מנתחים את התמונות עם Vision Brain",
    "vision_completed": "ניתוח Vision הושלם",
    "failed": "ניתוח Vision נכשל",
}
TRAIN_STAGE_HE = {
    "queued": "ממתינים לאימון",
    "loading_features": "טוענים את מאפייני ה-Vision",
    "training_models": "מאמנים את מודל העריכה",
    "locking_model": "נועלים את המודל לפני TEST",
    "testing_locked_set": "בודקים על TEST שלא השתתף באימון",
    "training_completed": "האימון והבדיקה הסתיימו",
    "failed": "האימון נכשל",
}


def _vision_job_dict(row):
    if not row:
        return None
    item = dict(row)
    item["details"] = json.loads(item.pop("details_json") or "{}")
    item["manifest"] = json.loads(item.pop("manifest_json") or "{}")
    item["stage_he"] = VISION_STAGE_HE.get(item["stage"], item["stage"])
    return item


def _training_run_dict(row):
    if not row:
        return None
    item = dict(row)
    item["details"] = json.loads(item.pop("details_json") or "{}")
    item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
    item["stage_he"] = TRAIN_STAGE_HE.get(item["stage"], item["stage"])
    return item


def _latest_vision_job(conn, profile_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
        (profile_id, user_id),
    ).fetchone()
    return _vision_job_dict(row)


def _latest_training_run(conn, profile_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM lightroom_training_runs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
        (profile_id, user_id),
    ).fetchone()
    return _training_run_dict(row)


def _update_vision_job(job_id: str, *, status=None, stage=None, progress=None, details=None, manifest=None, output_dir=None, error=None):
    fields = ["updated_at=?"]
    values = [utc_now()]
    if status is not None:
        fields.append("status=?"); values.append(status)
    if stage is not None:
        fields.append("stage=?"); values.append(stage)
    if progress is not None:
        fields.append("progress_percent=?"); values.append(int(progress))
    if details is not None:
        fields.append("details_json=?"); values.append(json.dumps(details, ensure_ascii=False))
    if manifest is not None:
        fields.append("manifest_json=?"); values.append(json.dumps(manifest, ensure_ascii=False))
    if output_dir is not None:
        fields.append("output_dir=?"); values.append(str(output_dir))
    if error is not None:
        fields.append("error=?"); values.append(str(error))
    values.append(job_id)
    with db() as conn:
        conn.execute(f"UPDATE lightroom_vision_jobs SET {', '.join(fields)} WHERE id=?", values)


def _run_vision_job(job_id: str, profile_id: str, build_id: str, user_id: str):
    try:
        with db() as conn:
            build = conn.execute(
                "SELECT * FROM lightroom_dataset_builds WHERE id=? AND profile_import_id=? AND user_id=?",
                (build_id, profile_id, user_id),
            ).fetchone()
        if not build or build["status"] != "completed":
            raise RuntimeError("Dataset is not ready for Vision preprocessing.")

        dataset_dir = Path(build["output_dir"])
        output_dir = AI_PROFILES_DIR / user_id / profile_id / "vision_features"
        output_dir.mkdir(parents=True, exist_ok=True)

        last_details = {}
        def progress_cb(stage, pct, details):
            nonlocal last_details
            last_details = details or {}
            _update_vision_job(
                job_id,
                status="building",
                stage=stage,
                progress=pct,
                details=last_details,
                output_dir=output_dir,
                error="",
            )

        manifest = build_vision_features(dataset_dir, output_dir, progress=progress_cb, batch_size=8)
        _update_vision_job(
            job_id,
            status="completed",
            stage="vision_completed",
            progress=100,
            details={**last_details, **manifest},
            manifest=manifest,
            output_dir=output_dir,
            error="",
        )
        with db() as conn:
            conn.execute(
                "UPDATE lightroom_profile_imports SET status='vision_ready', updated_at=? WHERE id=? AND user_id=?",
                (utc_now(), profile_id, user_id),
            )
    except Exception as exc:
        _update_vision_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
            details={"error": str(exc)},
        )


def _start_vision_job(profile_id: str, build_id: str, user_id: str):
    job_id = str(uuid.uuid4())
    now = utc_now()
    output_dir = AI_PROFILES_DIR / user_id / profile_id / "vision_features"
    with db() as conn:
        conn.execute(
            """
            INSERT INTO lightroom_vision_jobs
            (id,profile_import_id,dataset_build_id,user_id,status,stage,progress_percent,details_json,manifest_json,output_dir,error,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (job_id, profile_id, build_id, user_id, "queued", "queued", 1, "{}", "{}", str(output_dir), "", now, now),
        )
        row = conn.execute("SELECT * FROM lightroom_vision_jobs WHERE id=?", (job_id,)).fetchone()
    threading.Thread(
        target=_run_vision_job,
        args=(job_id, profile_id, build_id, user_id),
        daemon=True,
        name=f"prographer-vision-{job_id[:8]}",
    ).start()
    return _vision_job_dict(row)


def _update_training_run(run_id: str, *, status=None, stage=None, progress=None, details=None, metrics=None, model_path=None, error=None):
    fields = ["updated_at=?"]
    values = [utc_now()]
    if status is not None:
        fields.append("status=?"); values.append(status)
    if stage is not None:
        fields.append("stage=?"); values.append(stage)
    if progress is not None:
        fields.append("progress_percent=?"); values.append(int(progress))
    if details is not None:
        fields.append("details_json=?"); values.append(json.dumps(details, ensure_ascii=False))
    if metrics is not None:
        fields.append("metrics_json=?"); values.append(json.dumps(metrics, ensure_ascii=False))
    if model_path is not None:
        fields.append("model_path=?"); values.append(str(model_path))
    if error is not None:
        fields.append("error=?"); values.append(str(error))
    values.append(run_id)
    with db() as conn:
        conn.execute(f"UPDATE lightroom_training_runs SET {', '.join(fields)} WHERE id=?", values)


def _run_training(run_id: str, profile_id: str, vision_job_id: str, user_id: str):
    try:
        with db() as conn:
            vision_row = conn.execute(
                "SELECT * FROM lightroom_vision_jobs WHERE id=? AND profile_import_id=? AND user_id=?",
                (vision_job_id, profile_id, user_id),
            ).fetchone()
        if not vision_row or vision_row["status"] != "completed":
            raise RuntimeError("Vision preprocessing is not complete.")

        vision_dir = Path(vision_row["output_dir"])
        model_dir = AI_PROFILES_DIR / user_id / profile_id / "models"

        last_details = {}
        def progress_cb(stage, pct, details):
            nonlocal last_details
            last_details = details or {}
            _update_training_run(
                run_id,
                status="building",
                stage=stage,
                progress=pct,
                details=last_details,
                error="",
            )

        result = train_context_model(vision_dir, model_dir, progress=progress_cb)
        _update_training_run(
            run_id,
            status="completed",
            stage="training_completed",
            progress=100,
            details={**last_details, "target_count": result.get("target_count")},
            metrics=result,
            model_path=result.get("model_path") or "",
            error="",
        )
        with db() as conn:
            conn.execute(
                "UPDATE lightroom_profile_imports SET status='model_ready', updated_at=? WHERE id=? AND user_id=?",
                (utc_now(), profile_id, user_id),
            )
    except Exception as exc:
        _update_training_run(
            run_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
            details={"error": str(exc)},
        )


def _start_training(profile_id: str, vision_job_id: str, user_id: str):
    run_id = str(uuid.uuid4())
    now = utc_now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO lightroom_training_runs
            (id,profile_import_id,vision_job_id,user_id,status,stage,progress_percent,details_json,metrics_json,model_path,error,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (run_id, profile_id, vision_job_id, user_id, "queued", "queued", 1, "{}", "{}", "", "", now, now),
        )
        row = conn.execute("SELECT * FROM lightroom_training_runs WHERE id=?", (run_id,)).fetchone()
    threading.Thread(
        target=_run_training,
        args=(run_id, profile_id, vision_job_id, user_id),
        daemon=True,
        name=f"prographer-train-{run_id[:8]}",
    ).start()
    return _training_run_dict(row)



@app.get("/api/lightroom/profile-imports/{profile_import_id}/vision", dependencies=[Depends(require_user)])
def get_lightroom_profile_vision(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = conn.execute(
            "SELECT id,status FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")

        build = conn.execute(
            "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        audit = conn.execute(
            "SELECT * FROM lightroom_dataset_audits WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        job = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()

    if not build or build["status"] != "completed":
        raise HTTPException(409, "ה-Dataset עדיין לא מוכן")
    if not audit or audit["status"] != "completed":
        raise HTTPException(409, "בדיקת התקינות עדיין לא הסתיימה")
    audit_result = json.loads(audit["result_json"] or "{}")
    if not audit_result.get("passed"):
        raise HTTPException(409, "ה-Dataset לא עבר את בדיקת התקינות")

    if not job:
        return {"ok": True, "vision_job": _start_vision_job(profile_import_id, build["id"], user["id"])}

    return {"ok": True, "vision_job": _vision_job_dict(job)}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/vision/rebuild", dependencies=[Depends(require_user)])
def rebuild_lightroom_profile_vision(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        build = conn.execute(
            "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        audit = conn.execute(
            "SELECT * FROM lightroom_dataset_audits WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
    if not build or build["status"] != "completed":
        raise HTTPException(409, "ה-Dataset עדיין לא מוכן")
    if not audit or audit["status"] != "completed" or not json.loads(audit["result_json"] or "{}").get("passed"):
        raise HTTPException(409, "ה-Dataset לא עבר Integrity Audit")
    return {"ok": True, "vision_job": _start_vision_job(profile_import_id, build["id"], user["id"])}


@app.get("/api/lightroom/profile-imports/{profile_import_id}/training", dependencies=[Depends(require_user)])
def get_lightroom_profile_training(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = conn.execute(
            "SELECT id FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")
        run = conn.execute(
            "SELECT * FROM lightroom_training_runs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
    return {"ok": True, "training_run": _training_run_dict(run)}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/training/start", dependencies=[Depends(require_user)])
def start_lightroom_profile_training(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        vision = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        existing = conn.execute(
            "SELECT * FROM lightroom_training_runs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()

    if not vision or vision["status"] != "completed":
        raise HTTPException(409, "ניתוח Vision עדיין לא הושלם")
    if existing and existing["status"] in {"queued", "building"}:
        return {"ok": True, "training_run": _training_run_dict(existing)}

    return {"ok": True, "training_run": _start_training(profile_import_id, vision["id"], user["id"])}



@app.get("/api/lightroom/profile-imports/{profile_import_id}/evaluation", dependencies=[Depends(require_user)])
def get_lightroom_profile_evaluation(
    profile_import_id: str,
    refresh: bool = False,
    user=Depends(require_user),
):
    with db() as conn:
        profile = conn.execute(
            "SELECT id FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")

        vision = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        training = conn.execute(
            "SELECT * FROM lightroom_training_runs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()

    if not vision:
        raise HTTPException(409, "ניתוח Vision עדיין לא הושלם")
    if not training:
        raise HTTPException(409, "מודל מאומן עדיין לא קיים")

    vision_dir = Path(vision["output_dir"])
    model_path = Path(training["model_path"])
    evaluation_dir = AI_PROFILES_DIR / user["id"] / profile_import_id / "evaluation"
    cache_path = evaluation_dir / "evaluation_v1.json"

    if cache_path.exists() and not refresh:
        try:
            return {
                "ok": True,
                "cached": True,
                "evaluation": json.loads(cache_path.read_text(encoding="utf-8")),
            }
        except Exception:
            pass

    try:
        result = evaluate_context_model(
            vision_dir=vision_dir,
            model_path=model_path,
            output_dir=evaluation_dir,
        )
    except Exception as exc:
        raise HTTPException(500, f"Evaluation failed: {exc}") from exc

    return {"ok": True, "cached": False, "evaluation": result}



RECIPE_V2_STAGE_HE = {
    "queued": "ממתינים לאימון V2",
    "loading_recipe_v2": "טוענים את Recipe Intelligence V2",
    "training_recipe_v2": "מאמנים Context Model V2",
    "locking_v2_model": "נועלים את Model V2 לפני TEST",
    "testing_v2_locked_set": "בודקים את V2 על TEST הנעול",
    "recipe_v2_training_completed": "Context Model V2 מוכן",
    "failed": "אימון V2 נכשל",
}


def _training_v2_dict(row):
    if not row:
        return None
    item = dict(row)
    item["details"] = json.loads(item.pop("details_json") or "{}")
    item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
    item["stage_he"] = RECIPE_V2_STAGE_HE.get(item["stage"], item["stage"])
    return item


def _update_training_v2(run_id: str, *, status=None, stage=None, progress=None, details=None, metrics=None, model_path=None, error=None):
    fields = ["updated_at=?"]
    values = [utc_now()]
    if status is not None:
        fields.append("status=?"); values.append(status)
    if stage is not None:
        fields.append("stage=?"); values.append(stage)
    if progress is not None:
        fields.append("progress_percent=?"); values.append(int(progress))
    if details is not None:
        fields.append("details_json=?"); values.append(json.dumps(details, ensure_ascii=False))
    if metrics is not None:
        fields.append("metrics_json=?"); values.append(json.dumps(metrics, ensure_ascii=False))
    if model_path is not None:
        fields.append("model_path=?"); values.append(str(model_path))
    if error is not None:
        fields.append("error=?"); values.append(str(error))
    values.append(run_id)
    with db() as conn:
        conn.execute(f"UPDATE lightroom_training_v2_runs SET {', '.join(fields)} WHERE id=?", values)


def _recipe_v2_paths(profile_id: str, user_id: str):
    root = AI_PROFILES_DIR / user_id / profile_id
    return {
        "root": root,
        "recipe_dir": root / "recipe_v2",
        "report": root / "recipe_v2" / "report.json",
        "evaluation_v1": root / "evaluation" / "evaluation_v1.json",
        "models": root / "models",
    }


def _ensure_recipe_v2(profile_id: str, user_id: str, refresh: bool = False):
    paths = _recipe_v2_paths(profile_id, user_id)
    if paths["report"].exists() and not refresh:
        try:
            cached = json.loads(paths["report"].read_text(encoding="utf-8"))
            if (
                cached.get("recipe_version") == "prographer-recipe-v2.2"
                and isinstance(cached.get("learnability"), dict)
                and isinstance(cached.get("provenance"), dict)
            ):
                return cached
        except Exception:
            pass
        # Older Recipe V2 report: rebuild only the recipe analysis from the
        # existing Dataset + Vision features. RAW/CLIP work is not repeated.

    with db() as conn:
        build = conn.execute(
            "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_id, user_id),
        ).fetchone()
        vision = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_id, user_id),
        ).fetchone()

    if not build:
        raise HTTPException(409, "Dataset מוכן לא נמצא")
    if not vision:
        raise HTTPException(409, "Vision features מוכנים לא נמצאו")

    return build_recipe_v2_dataset(
        Path(build["output_dir"]),
        Path(vision["output_dir"]),
        paths["recipe_dir"],
    )


def _run_training_v2(run_id: str, profile_id: str, vision_job_id: str, user_id: str):
    try:
        report = _ensure_recipe_v2(profile_id, user_id, refresh=False)
        paths = _recipe_v2_paths(profile_id, user_id)

        last_details = {}
        def progress_cb(stage, pct, details):
            nonlocal last_details
            last_details = details or {}
            _update_training_v2(
                run_id,
                status="building",
                stage=stage,
                progress=pct,
                details=last_details,
                error="",
            )

        result = train_context_model_v2(
            recipe_v2_dir=paths["recipe_dir"],
            model_dir=paths["models"],
            v1_evaluation_path=paths["evaluation_v1"],
            progress=progress_cb,
        )
        _update_training_v2(
            run_id,
            status="completed",
            stage="recipe_v2_training_completed",
            progress=100,
            details={**last_details, "target_count": result.get("target_count")},
            metrics=result,
            model_path=result.get("model_path") or "",
            error="",
        )
    except Exception as exc:
        _update_training_v2(
            run_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
            details={"error": str(exc)},
        )


def _start_training_v2(profile_id: str, vision_job_id: str, user_id: str):
    run_id = str(uuid.uuid4())
    now = utc_now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO lightroom_training_v2_runs
            (id,profile_import_id,vision_job_id,user_id,status,stage,progress_percent,details_json,metrics_json,model_path,error,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (run_id, profile_id, vision_job_id, user_id, "queued", "queued", 1, "{}", "{}", "", "", now, now),
        )
        row = conn.execute("SELECT * FROM lightroom_training_v2_runs WHERE id=?", (run_id,)).fetchone()

    threading.Thread(
        target=_run_training_v2,
        args=(run_id, profile_id, vision_job_id, user_id),
        daemon=True,
        name=f"prographer-train-v2-{run_id[:8]}",
    ).start()
    return _training_v2_dict(row)


@app.get("/api/lightroom/profile-imports/{profile_import_id}/recipe-v2", dependencies=[Depends(require_user)])
def get_lightroom_profile_recipe_v2(
    profile_import_id: str,
    refresh: bool = False,
    user=Depends(require_user),
):
    with db() as conn:
        profile = conn.execute(
            "SELECT id FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")

    report = _ensure_recipe_v2(profile_import_id, user["id"], refresh=refresh)
    return {"ok": True, "report": report}


@app.get("/api/lightroom/profile-imports/{profile_import_id}/training-v2", dependencies=[Depends(require_user)])
def get_lightroom_profile_training_v2(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        run = conn.execute(
            "SELECT * FROM lightroom_training_v2_runs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
    return {"ok": True, "training_run": _training_v2_dict(run)}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/training-v2/start", dependencies=[Depends(require_user)])
def start_lightroom_profile_training_v2(profile_import_id: str, user=Depends(require_user)):
    _ensure_recipe_v2(profile_import_id, user["id"], refresh=False)

    with db() as conn:
        vision = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        existing = conn.execute(
            "SELECT * FROM lightroom_training_v2_runs WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()

    if not vision:
        raise HTTPException(409, "Vision preprocessing עדיין לא הושלם")
    if existing and existing["status"] in {"queued", "building"}:
        return {"ok": True, "training_run": _training_v2_dict(existing)}

    return {"ok": True, "training_run": _start_training_v2(profile_import_id, vision["id"], user["id"])}


def _production_profile_paths(profile_id: str, user_id: str):
    root = AI_PROFILES_DIR / user_id / profile_id
    production = root / "production"
    return {
        "root": root,
        "production": production,
        "manifest": production / "production_profile_v1.json",
        "artifact": production / "production_profile_v1.joblib",
        "v1_fallback": root / "models" / "context_model_v1.joblib",
        "v2_fallback": root / "models" / "context_model_v2.joblib",
    }


def _register_current_production_profile(
    profile_id: str,
    user_id: str,
    manifest: dict,
):
    paths = _production_profile_paths(profile_id, user_id)
    with db() as conn:
        profile = conn.execute(
            """
            SELECT id,profile_name
            FROM lightroom_profile_imports
            WHERE id=? AND user_id=?
            """,
            (profile_id, user_id),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")

        registry = register_production_profile_snapshot(
            conn,
            data_dir=DATA_DIR,
            ai_profiles_dir=AI_PROFILES_DIR,
            user_id=user_id,
            source_profile_import_id=profile_id,
            profile_name=profile["profile_name"],
            production_manifest_path=paths["manifest"],
            production_artifact_path=paths["artifact"],
        )
    return registry


def _resolve_model_artifact(stored_path: str, fallback: Path) -> Path:
    stored = Path(stored_path) if stored_path else None
    if stored and stored.exists():
        return stored
    if fallback.exists():
        return fallback
    raise RuntimeError(f"Model artifact not found: {stored_path or fallback}")


def _ensure_production_profile(profile_id: str, user_id: str, refresh: bool = False):
    with db() as conn:
        profile = conn.execute(
            "SELECT id FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_id, user_id),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")

        v1 = conn.execute(
            "SELECT * FROM lightroom_training_runs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_id, user_id),
        ).fetchone()
        v2 = conn.execute(
            "SELECT * FROM lightroom_training_v2_runs WHERE profile_import_id=? AND user_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (profile_id, user_id),
        ).fetchone()

    if not v1:
        raise HTTPException(409, "Context Model V1 מוכן לא נמצא")
    if not v2:
        raise HTTPException(409, "Context Model V2 מוכן לא נמצא")

    recipe_paths = _recipe_v2_paths(profile_id, user_id)
    _ensure_recipe_v2(profile_id, user_id, refresh=False)
    paths = _production_profile_paths(profile_id, user_id)

    if paths["manifest"].exists() and paths["artifact"].exists() and not refresh:
        try:
            cached = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            sources = cached.get("source_runs") or {}
            if (
                cached.get("profile_format") == "prographer-production-ai-profile-v1"
                and cached.get("recipe_contract", {}).get("version") == "prographer-edit-recipe-v1"
                and sources.get("context_model_v1") == v1["id"]
                and sources.get("context_model_v2") == v2["id"]
            ):
                _register_current_production_profile(profile_id, user_id, cached)
                return cached
        except Exception:
            pass

    try:
        v1_model = _resolve_model_artifact(v1["model_path"], paths["v1_fallback"])
        v2_model = _resolve_model_artifact(v2["model_path"], paths["v2_fallback"])
        manifest = build_production_profile_v1(
            profile_import_id=profile_id,
            user_id=user_id,
            recipe_v2_dir=recipe_paths["recipe_dir"],
            recipe_report_path=recipe_paths["report"],
            v1_model_path=v1_model,
            v2_model_path=v2_model,
            output_dir=paths["production"],
            source_v1_run_id=v1["id"],
            source_v2_run_id=v2["id"],
        )
        _register_current_production_profile(profile_id, user_id, manifest)
        return manifest
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Production Profile build failed: {exc}") from exc


@app.get("/api/ai/recipe-contract/v1", dependencies=[Depends(require_user)])
def get_recipe_contract_v1(user=Depends(require_user)):
    return {"ok": True, "contract": recipe_contract_public()}


@app.get("/api/lightroom/profile-imports/{profile_import_id}/production-profile", dependencies=[Depends(require_user)])
def get_production_profile(profile_import_id: str, refresh: bool = False, user=Depends(require_user)):
    profile = _ensure_production_profile(profile_import_id, user["id"], refresh=refresh)
    return {"ok": True, "production_profile": profile}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/production-profile/rebuild", dependencies=[Depends(require_user)])
def rebuild_production_profile(profile_import_id: str, user=Depends(require_user)):
    profile = _ensure_production_profile(profile_import_id, user["id"], refresh=True)
    return {"ok": True, "production_profile": profile}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/production-profile/register", dependencies=[Depends(require_user)])
def register_production_profile_version(profile_import_id: str, user=Depends(require_user)):
    manifest = _ensure_production_profile(profile_import_id, user["id"], refresh=False)
    registry = _register_current_production_profile(
        profile_import_id,
        user["id"],
        manifest,
    )
    return {"ok": True, "registry": registry}



def _retraining_status_payload(user_id: str) -> dict:
    with db() as conn:
        active_registry = get_default_active_profile(conn, user_id=user_id)
        if not active_registry:
            return {
                "ok": True,
                "retraining_format": RETRAINING_FORMAT,
                "active_profile": None,
                "readiness": {
                    "sample_count": 0,
                    "approved_count": 0,
                    "corrected_count": 0,
                    "minimum_samples": MIN_TOTAL_SAMPLES,
                    "minimum_new_samples": 0,
                    "new_samples_since_active": 0,
                    "remaining_samples": MIN_TOTAL_SAMPLES,
                    "ready": False,
                    "active_is_adaptive": False,
                    "recipe_contract_version": "prographer-edit-recipe-v1",
                },
                "latest_run": None,
                "candidate_version": None,
            }

        readiness = retraining_readiness(
            conn,
            user_id=user_id,
            registry_id=active_registry["id"],
        )
        latest = latest_retraining_run(
            conn,
            user_id=user_id,
            registry_id=active_registry["id"],
        )

        candidate = None
        if latest and latest.get("candidate_version_id"):
            row = conn.execute(
                """
                SELECT *
                FROM ai_profile_versions
                WHERE id=? AND registry_id=? AND user_id=?
                """,
                (
                    latest["candidate_version_id"],
                    active_registry["id"],
                    user_id,
                ),
            ).fetchone()
            if row:
                candidate = {
                    "id": row["id"],
                    "version_number": int(row["version_number"]),
                    "status": row["status"],
                    "recipe_contract_version": row["recipe_contract_version"],
                    "summary": json.loads(row["summary_json"] or "{}"),
                    "created_at": row["created_at"],
                    "activated_at": row["activated_at"],
                }

    return {
        "ok": True,
        "retraining_format": RETRAINING_FORMAT,
        "active_profile": _active_profile_summary(active_registry),
        "readiness": readiness,
        "latest_run": latest,
        "candidate_version": candidate,
    }


@app.get("/api/ai/profile/overview", dependencies=[Depends(require_user)])
def get_photographer_ai_profile_overview(user=Depends(require_user)):
    with db() as conn:
        return photographer_profile_overview(
            conn,
            user_id=user["id"],
        )


@app.get("/api/ai/retraining/status", dependencies=[Depends(require_user)])
def get_ai_retraining_status(user=Depends(require_user)):
    return _retraining_status_payload(user["id"])


def _run_adaptive_retraining_job(run_id: str, user_id: str):
    try:
        with db() as conn:
            active_registry = get_default_active_profile(conn, user_id=user_id)
            if not active_registry:
                raise RuntimeError("No ACTIVE AI Profile.")

            run = conn.execute(
                "SELECT * FROM ai_retraining_runs WHERE id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
            if not run:
                return

            # Pin the job to the Profile version that was active when created.
            if run["parent_version_id"] != active_registry["active_version"]["id"]:
                raise RuntimeError(
                    "The ACTIVE Profile changed before retraining started. Start a new retraining run."
                )

            update_retraining_run(
                conn,
                run_id=run_id,
                status="running",
                stage="building_learning_split",
                progress_percent=10,
            )

        with db() as conn:
            active_registry = get_default_active_profile(conn, user_id=user_id)
            result = build_adaptive_candidate(
                conn=conn,
                data_dir=DATA_DIR,
                ai_profiles_dir=AI_PROFILES_DIR,
                user_id=user_id,
                active_registry=active_registry,
                run_id=run_id,
            )

            status = result["status"]
            if status == "no_improvement":
                update_retraining_run(
                    conn,
                    run_id=run_id,
                    status="no_improvement",
                    stage="completed",
                    progress_percent=100,
                    sample_count=result["sample_count"],
                    train_count=result["train_count"],
                    validation_count=result["validation_count"],
                    adapted_targets=[],
                    metrics=result["metrics"],
                )
                return

            candidate = result["candidate_version"]
            update_retraining_run(
                conn,
                run_id=run_id,
                status="completed",
                stage="candidate_ready",
                progress_percent=100,
                sample_count=result["sample_count"],
                train_count=result["train_count"],
                validation_count=result["validation_count"],
                adapted_targets=result["adapted_targets"],
                metrics=result["metrics"],
                candidate_version_id=candidate["id"],
            )

    except Exception as exc:
        with db() as conn:
            try:
                update_retraining_run(
                    conn,
                    run_id=run_id,
                    status="failed",
                    stage="failed",
                    progress_percent=100,
                    error=str(exc),
                )
            except Exception:
                pass


@app.post("/api/ai/retraining/start", dependencies=[Depends(require_user)])
def start_ai_retraining(user=Depends(require_user)):
    with db() as conn:
        active_registry = get_default_active_profile(conn, user_id=user["id"])
        if not active_registry:
            raise HTTPException(409, "אין AI Profile פעיל")

        readiness = retraining_readiness(
            conn,
            user_id=user["id"],
            registry_id=active_registry["id"],
        )
        if not readiness["ready"]:
            raise HTTPException(
                409,
                f"נדרשות לפחות {MIN_TOTAL_SAMPLES} החלטות למידה. חסרות {readiness['remaining_samples']}.",
            )

        running = active_retraining_run(
            conn,
            user_id=user["id"],
            registry_id=active_registry["id"],
        )
        if running:
            return {
                "ok": True,
                "started": False,
                "run": running,
                "status": _retraining_status_payload(user["id"]),
            }

        active = active_registry["active_version"]
        run = create_retraining_run(
            conn,
            user_id=user["id"],
            registry_id=active_registry["id"],
            parent_version_id=active["id"],
            parent_version_number=int(active["version_number"]),
            sample_count=int(readiness["sample_count"]),
        )

    threading.Thread(
        target=_run_adaptive_retraining_job,
        args=(run["id"], user["id"]),
        daemon=True,
        name=f"prographer-retraining-{run['id'][:8]}",
    ).start()

    return {
        "ok": True,
        "started": True,
        "run": run,
        "active_profile": _active_profile_summary(active_registry),
    }


@app.on_event("startup")
def recover_interrupted_retraining_jobs():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id FROM ai_retraining_runs
            WHERE status IN ('queued','running')
            """
        ).fetchall()
        for row in rows:
            update_retraining_run(
                conn,
                run_id=row["id"],
                status="failed",
                stage="interrupted",
                progress_percent=100,
                error="Local Engine restarted during retraining. Start retraining again; learning samples are safe.",
            )


@app.get("/api/ai/profiles", dependencies=[Depends(require_user)])
def list_ai_profile_registries(user=Depends(require_user)):
    with db() as conn:
        profiles = list_registries(conn, user_id=user["id"])
    return {"ok": True, "profiles": profiles}


@app.get("/api/ai/profiles/active", dependencies=[Depends(require_user)])
def get_active_ai_profile(user=Depends(require_user)):
    with db() as conn:
        profile = get_default_active_profile(conn, user_id=user["id"])
    if not profile:
        raise HTTPException(404, "אין עדיין AI Profile פעיל")
    return {"ok": True, "profile": profile}


@app.get("/api/ai/profiles/{registry_id}", dependencies=[Depends(require_user)])
def get_ai_profile_registry(registry_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = get_registry(conn, registry_id=registry_id, user_id=user["id"])
    if not profile:
        raise HTTPException(404, "AI Profile לא נמצא")
    return {"ok": True, "profile": profile}


@app.post("/api/ai/profiles/{registry_id}/make-default", dependencies=[Depends(require_user)])
def make_ai_profile_default(registry_id: str, user=Depends(require_user)):
    try:
        with db() as conn:
            profile = set_default_registry(
                conn,
                registry_id=registry_id,
                user_id=user["id"],
            )
    except KeyError:
        raise HTTPException(404, "AI Profile לא נמצא")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "profile": profile}


@app.post("/api/ai/profiles/{registry_id}/versions/{version_id}/activate", dependencies=[Depends(require_user)])
def activate_ai_profile_version(registry_id: str, version_id: str, user=Depends(require_user)):
    try:
        with db() as conn:
            profile = activate_version(
                conn,
                registry_id=registry_id,
                version_id=version_id,
                user_id=user["id"],
            )
    except KeyError as exc:
        code = str(exc).strip("'")
        if code == "registry_not_found":
            raise HTTPException(404, "AI Profile לא נמצא")
        raise HTTPException(404, "גרסת AI Profile לא נמצאה")
    return {"ok": True, "profile": profile}


def _resolve_active_profile_for_inference(user_id: str):
    """
    Stage 3 bridge. The future event inference engine calls only this resolver,
    so READY candidates can never be used accidentally.
    """
    with db() as conn:
        return resolve_active_artifact(
            conn,
            data_dir=DATA_DIR,
            user_id=user_id,
        )


def _background_prepare_production_profiles():
    # Upgrade bridge for existing completed V1/V2 profiles.  This runs in a
    # daemon thread so backend startup is never blocked by model loading.
    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT p.id, p.user_id
                FROM lightroom_profile_imports p
                WHERE EXISTS (
                    SELECT 1 FROM lightroom_training_runs v1
                    WHERE v1.profile_import_id=p.id AND v1.user_id=p.user_id AND v1.status='completed'
                )
                  AND EXISTS (
                    SELECT 1 FROM lightroom_training_v2_runs v2
                    WHERE v2.profile_import_id=p.id AND v2.user_id=p.user_id AND v2.status='completed'
                )
                """
            ).fetchall()
        for row in rows:
            try:
                _ensure_production_profile(row["id"], row["user_id"], refresh=False)
            except Exception as exc:
                print(f"[Production Profile] {row['id']}: {exc}")
    except Exception as exc:
        print(f"[Production Profile] startup bridge failed: {exc}")


@app.on_event("startup")
def prepare_production_profiles_on_startup():
    threading.Thread(
        target=_background_prepare_production_profiles,
        daemon=True,
        name="prographer-production-profile-upgrade",
    ).start()


@app.get("/api/lightroom/catalogs/scan", dependencies=[Depends(require_user)])
def scan_lightroom_catalogs(user=Depends(require_user)):
    catalogs = scan_catalogs()
    return {"ok": True, "catalogs": catalogs, "count": len(catalogs), "searched_roots": [{"label": label, "path": str(path)} for label, path in catalog_roots()]}

@app.post("/api/lightroom/catalogs/analyze", dependencies=[Depends(require_user)])
def analyze_lightroom_catalog(payload: LightroomCatalogAnalyzeRequest, user=Depends(require_user)):
    try:
        return analyze_catalog(payload.path.strip())
    except LightroomCatalogError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get("/api/lightroom/profile-imports", dependencies=[Depends(require_user)])
def list_lightroom_profile_imports(user=Depends(require_user)):
    with db() as conn:
        rows = conn.execute("SELECT id, profile_name, catalog_path, catalog_name, selected_collections_json, status, created_at, updated_at FROM lightroom_profile_imports WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["selected_collections"] = json.loads(item.pop("selected_collections_json") or "[]")
            item["dataset_build"] = _dataset_build_for_profile(conn, item["id"], user["id"])
            item["dataset_audit"] = _dataset_audit_for_profile(conn, item["id"], user["id"])
            item["vision_job"] = _latest_vision_job(conn, item["id"], user["id"])
            item["training_run"] = _latest_training_run(conn, item["id"], user["id"])
            result.append(item)
    return result

@app.get("/api/lightroom/profile-imports/{profile_import_id}/dataset-build", dependencies=[Depends(require_user)])
def get_lightroom_dataset_build(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = conn.execute("SELECT id,profile_name,status FROM lightroom_profile_imports WHERE id=? AND user_id=?", (profile_import_id, user["id"])).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")
        build = _dataset_build_for_profile(conn, profile_import_id, user["id"])
    if not build:
        raise HTTPException(404, "בניית Dataset עדיין לא התחילה")
    return {"ok": True, "profile": dict(profile), "dataset_build": build}

@app.get("/api/lightroom/profile-imports/{profile_import_id}/dataset-audit", dependencies=[Depends(require_user)])
def get_lightroom_dataset_audit(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = conn.execute(
            "SELECT id,profile_name,status FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")
        build_row = conn.execute(
            "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not build_row or build_row["status"] != "completed":
            raise HTTPException(409, "ה-Dataset עדיין לא מוכן לבדיקת תקינות")
        audit = _dataset_audit_for_profile(conn, profile_import_id, user["id"])

    if not audit:
        audit = _start_lightroom_dataset_audit(profile_import_id, build_row["id"], user["id"])

    return {"ok": True, "profile": dict(profile), "dataset_audit": audit}


@app.post("/api/lightroom/profile-imports/{profile_import_id}/dataset-audit/rebuild", dependencies=[Depends(require_user)])
def rebuild_lightroom_dataset_audit(profile_import_id: str, user=Depends(require_user)):
    with db() as conn:
        profile = conn.execute(
            "SELECT id FROM lightroom_profile_imports WHERE id=? AND user_id=?",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not profile:
            raise HTTPException(404, "פרופיל AI לא נמצא")
        build = conn.execute(
            "SELECT * FROM lightroom_dataset_builds WHERE profile_import_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (profile_import_id, user["id"]),
        ).fetchone()
        if not build or build["status"] != "completed":
            raise HTTPException(409, "ה-Dataset עדיין לא מוכן")
    audit = _start_lightroom_dataset_audit(profile_import_id, build["id"], user["id"])
    return {"ok": True, "dataset_audit": audit}


@app.post("/api/lightroom/profile-imports", dependencies=[Depends(require_user)])
def create_lightroom_profile_import(payload: LightroomProfileImportCreate, user=Depends(require_user)):
    try:
        analysis = payload.analysis or analyze_catalog(payload.catalog_path.strip())
    except LightroomCatalogError as exc:
        raise HTTPException(400, str(exc)) from exc
    catalog = analysis.get("catalog") or {}
    now = utc_now()
    import_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute("INSERT INTO lightroom_profile_imports (id, user_id, profile_name, catalog_path, catalog_name, selected_collections_json, analysis_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (import_id, user["id"], payload.profile_name.strip(), payload.catalog_path.strip(), catalog.get("name") or Path(payload.catalog_path).name, json.dumps(payload.selected_collections, ensure_ascii=False), json.dumps(analysis, ensure_ascii=False), "dataset_building", now, now))
    build = _start_lightroom_dataset_build(import_id, user["id"])
    return {
        "ok": True,
        "id": import_id,
        "profile_name": payload.profile_name.strip(),
        "status": "dataset_building",
        "selected_collections": payload.selected_collections,
        "dataset_build": build,
        "message_he": "הפרופיל נשמר. ProGrapher התחיל להכין את ה-Dataset באופן אוטומטי.",
    }

@app.on_event("startup")
def resume_pending_lightroom_dataset_builds():
    """
    Upgrade bridge + crash recovery.

    V1.3.3.1 also repairs the V1.3.3 Lightroom pairing bug: a completed build
    with zero verified pairs is not a valid Dataset. Such profiles are
    automatically rebuilt after the Develop-settings join fix.
    """
    with db() as conn:
        profiles = conn.execute(
            """
            SELECT id,user_id,status
            FROM lightroom_profile_imports
            WHERE status IN (
                'ready_for_dataset_mapping',
                'dataset_building',
                'dataset_ready'
            )
            ORDER BY created_at ASC
            """
        ).fetchall()

    for profile in profiles:
        should_start = False

        with db() as conn:
            latest = conn.execute(
                """
                SELECT *
                FROM lightroom_dataset_builds
                WHERE profile_import_id=? AND user_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (profile["id"], profile["user_id"]),
            ).fetchone()

            if latest and latest["status"] == "completed":
                try:
                    manifest = json.loads(latest["manifest_json"] or "{}")
                except Exception:
                    manifest = {}

                valid_pairs = int(manifest.get("valid_pairs") or 0)

                if valid_pairs > 0:
                    conn.execute(
                        "UPDATE lightroom_profile_imports SET status='dataset_ready', updated_at=? WHERE id=?",
                        (utc_now(), profile["id"]),
                    )
                    continue

                # V1.3.3 could incorrectly mark 0-pair datasets as complete.
                conn.execute(
                    """
                    UPDATE lightroom_dataset_builds
                    SET status='failed',
                        stage='failed',
                        error=?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        "Dataset contained 0 verified pairs and was rebuilt automatically after the Lightroom pairing fix.",
                        utc_now(),
                        latest["id"],
                    ),
                )
                should_start = True

            elif latest and latest["status"] in {"queued", "building"}:
                conn.execute(
                    """
                    UPDATE lightroom_dataset_builds
                    SET status='failed',stage='failed',error=?,updated_at=?
                    WHERE id=?
                    """,
                    (
                        "Local Engine restarted; build restarted automatically.",
                        utc_now(),
                        latest["id"],
                    ),
                )
                should_start = True

            elif profile["status"] in {"ready_for_dataset_mapping", "dataset_building"}:
                should_start = True

            if should_start:
                conn.execute(
                    "UPDATE lightroom_profile_imports SET status='dataset_building', updated_at=? WHERE id=?",
                    (utc_now(), profile["id"]),
                )

        if should_start:
            _start_lightroom_dataset_build(profile["id"], profile["user_id"])


    # V1.3.4.1 upgrade/recovery bridge:
    # - completed Datasets get an audit automatically;
    # - an audit that was queued/building when the Local Engine stopped is
    #   impossible to resume because its worker thread died with the process,
    #   so mark that record interrupted and start a fresh audit.
    with db() as conn:
        completed = conn.execute(
            """
            SELECT p.id profile_id, p.user_id, b.id build_id
            FROM lightroom_profile_imports p
            JOIN lightroom_dataset_builds b
              ON b.profile_import_id = p.id
             AND b.user_id = p.user_id
            WHERE b.status='completed'
              AND b.id = (
                  SELECT b2.id
                  FROM lightroom_dataset_builds b2
                  WHERE b2.profile_import_id=p.id
                    AND b2.user_id=p.user_id
                  ORDER BY b2.created_at DESC
                  LIMIT 1
              )
            """
        ).fetchall()

    for row in completed:
        should_start_audit = False

        with db() as conn:
            audit = conn.execute(
                """
                SELECT *
                FROM lightroom_dataset_audits
                WHERE profile_import_id=?
                  AND dataset_build_id=?
                  AND user_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (row["profile_id"], row["build_id"], row["user_id"]),
            ).fetchone()

            if not audit:
                should_start_audit = True
            elif audit["status"] in {"queued", "building"}:
                conn.execute(
                    """
                    UPDATE lightroom_dataset_audits
                    SET status='failed',
                        stage='interrupted',
                        progress_percent=100,
                        error=?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        "Local Engine restarted while Dataset Integrity Audit was running; audit restarted automatically.",
                        utc_now(),
                        audit["id"],
                    ),
                )
                should_start_audit = True

        if should_start_audit:
            _start_lightroom_dataset_audit(
                row["profile_id"],
                row["build_id"],
                row["user_id"],
            )


@app.get("/api/system", dependencies=[Depends(require_user)])
def system_info():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(DATA_DIR))
    return {
        "cpu": {
            "percent": psutil.cpu_percent(interval=0.15),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
        },
        "ram": {
            "total_bytes": memory.total,
            "used_bytes": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "path": str(DATA_DIR),
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "gpu": system_gpu_info(),
        "raw_support": RAW_ENABLED,
        "exif_support": EXIFREAD_ENABLED,
    }

@app.get("/api/stats", dependencies=[Depends(require_user)])
def stats(user=Depends(require_user)):
    uid=user["id"]
    with db() as conn:
        events=conn.execute("SELECT COUNT(*) c FROM events WHERE user_id = ?",(uid,)).fetchone()["c"]
        photos=conn.execute("SELECT COUNT(*) c FROM photos p INNER JOIN events e ON e.id=p.event_id WHERE e.user_id = ?",(uid,)).fetchone()["c"]
        active=conn.execute("SELECT COUNT(*) c FROM feedback f INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id = ?",(uid,)).fetchone()["c"]
        archived=conn.execute("SELECT COUNT(*) c FROM style_learning_archive WHERE user_id = ?",(uid,)).fetchone()["c"]
        accepted=conn.execute("""SELECT COUNT(*) c FROM (SELECT f.verdict FROM feedback f INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=? UNION ALL SELECT verdict FROM style_learning_archive WHERE user_id=?) WHERE verdict IN ('approved','selected_default','selected_final','מושלם')""",(uid,uid)).fetchone()["c"]
        decided=conn.execute("""SELECT COUNT(*) c FROM (SELECT f.verdict FROM feedback f INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=? UNION ALL SELECT verdict FROM style_learning_archive WHERE user_id=?) WHERE verdict IN ('approved','selected_default','selected_final','corrected','מושלם')""",(uid,uid)).fetchone()["c"]
        pairs=conn.execute("SELECT COUNT(*) c FROM style_pairs WHERE user_id = ?",(uid,)).fetchone()["c"]
        production_learning = learning_summary(conn, user_id=uid)

    production_total = int(production_learning.get("sample_count") or 0)
    legacy_acceptance = round((accepted/decided)*100,1) if decided else None
    effective_acceptance = (
        production_learning.get("acceptance_rate")
        if production_total > 0
        else legacy_acceptance
    )
    effective_accepted = (
        int(production_learning.get("approved_count") or 0)
        if production_total > 0
        else accepted
    )
    return {
        "events": events,
        "photos": photos,
        "feedback_total": production_total if production_total > 0 else active+archived,
        "archived_learning_samples": archived,
        "perfect_without_change": effective_accepted,
        "acceptance_rate": effective_acceptance,
        "style_pairs": pairs,
        "production_learning_samples": production_total,
        "production_corrected_samples": int(production_learning.get("corrected_count") or 0),
        "production_learning_format": LEARNING_SAMPLE_FORMAT,
    }


@app.get("/api/events", dependencies=[Depends(require_user)])
def list_events(user=Depends(require_user)):
    with db() as conn:
        rows=conn.execute("""SELECT e.*,COUNT(p.id) AS photo_count,SUM(CASE WHEN p.preview_path IS NOT NULL THEN 1 ELSE 0 END) AS preview_count FROM events e LEFT JOIN photos p ON p.event_id=e.id WHERE e.user_id=? GROUP BY e.id ORDER BY e.created_at DESC""",(user["id"],)).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/events", dependencies=[Depends(require_user)])
def create_event(payload: EventCreate, user=Depends(require_user)):
    event_id=str(uuid.uuid4()); now=utc_now(); event_dirs(event_id)
    with db() as conn:
        conn.execute("""INSERT INTO events (id,name,event_type,event_date,style_note,status,created_at,updated_at,user_id) VALUES (?,?,?,?,?,?,?,?,?)""",(event_id,payload.name.strip(),payload.event_type,payload.event_date,payload.style_note,"ממתין לתמונות",now,now,user["id"]))
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row)

@app.get("/api/events/{event_id}", dependencies=[Depends(require_user)])
def get_event(event_id: str, request: Request):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")
        photos = conn.execute(
            "SELECT * FROM photos WHERE event_id = ? ORDER BY created_at ASC",
            (event_id,),
        ).fetchall()

    return {
        "event": dict(event),
        "photos": [row_to_photo(request, p) for p in photos],
    }

@app.patch("/api/events/{event_id}", dependencies=[Depends(require_user)])
def update_event(event_id: str, payload: EventUpdate):
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "לא נשלחו שינויים")

    fields["updated_at"] = utc_now()
    clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [event_id]

    with db() as conn:
        exists = conn.execute("SELECT id, user_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not exists:
            raise HTTPException(404, "האירוע לא נמצא")
        conn.execute(f"UPDATE events SET {clause} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row)



@app.get("/api/events/{event_id}/completion/status", dependencies=[Depends(require_user)])
def get_event_completion_status(event_id: str, user=Depends(require_user)):
    try:
        with db() as conn:
            status = event_completion_status(
                conn,
                event_id=event_id,
                user_id=user["id"],
            )
    except KeyError:
        raise HTTPException(404, "האירוע לא נמצא")
    return {
        "ok": True,
        "export_format": EXPORT_FORMAT,
        **status,
    }


@app.post("/api/events/{event_id}/completion/approve-remaining", dependencies=[Depends(require_user)])
def approve_remaining_event_photos(event_id: str, user=Depends(require_user)):
    """
    Explicit bulk approval.  Nothing is auto-approved silently.

    It is intended for the normal event workflow: inspect problem photos,
    correct what needs correction, then approve the remaining AI edits at once.
    """
    with db() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id=? AND user_id=?",
            (event_id, user["id"]),
        ).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        photos = conn.execute(
            """
            SELECT *
            FROM photos
            WHERE event_id=?
            ORDER BY created_at ASC
            """,
            (event_id,),
        ).fetchall()

        decisions = {
            row["source_photo_id"]: row
            for row in conn.execute(
                """
                SELECT *
                FROM ai_learning_samples
                WHERE user_id=? AND source_event_id=? AND is_current=1
                ORDER BY created_at ASC
                """,
                (user["id"], event_id),
            ).fetchall()
            if row["source_photo_id"]
        }

        predictions_rows = conn.execute(
            """
            SELECT *
            FROM photo_ai_predictions
            WHERE event_id=? AND user_id=?
            ORDER BY created_at DESC
            """,
            (event_id, user["id"]),
        ).fetchall()

        predictions = {}
        for row in predictions_rows:
            if row["photo_id"] in predictions:
                continue
            item = dict(row)
            item["recipe"] = json.loads(item.pop("recipe_json") or "{}")
            item["provenance"] = json.loads(item.pop("provenance_json") or "{}")
            predictions[row["photo_id"]] = item

        remaining = [row for row in photos if row["id"] not in decisions]
        missing_predictions = [
            row["original_name"]
            for row in remaining
            if row["id"] not in predictions
        ]
        if missing_predictions:
            raise HTTPException(
                409,
                f"{len(missing_predictions)} תמונות עדיין לא קיבלו תחזית AI. יש להשלים קודם את עריכת האירוע.",
            )

        # Preflight brain rows too, so we never half-approve an event.
        brain_by_prediction = {}
        for photo in remaining:
            prediction = predictions[photo["id"]]
            brain = conn.execute(
                """
                SELECT *
                FROM photo_brain_vision
                WHERE id=? AND photo_id=?
                """,
                (prediction["brain_analysis_id"], photo["id"]),
            ).fetchone()
            if not brain:
                raise HTTPException(
                    409,
                    f"Vision data חסר עבור {photo['original_name']}.",
                )
            brain_by_prediction[prediction["id"]] = brain

        approved = 0
        for photo in remaining:
            prediction = predictions[photo["id"]]
            brain = brain_by_prediction[prediction["id"]]
            process_family = _prediction_process_family(prediction)

            save_learning_decision(
                conn,
                user_id=user["id"],
                photo_row=photo,
                brain_row=brain,
                prediction=prediction,
                verdict="approved",
                photographer_recipe=None,
                process_family=process_family,
                note="Bulk approved during event completion",
            )
            conn.execute(
                """
                UPDATE photos
                SET status='אושר', updated_at=?
                WHERE id=?
                """,
                (utc_now(), photo["id"]),
            )
            approved += 1

        status = event_completion_status(
            conn,
            event_id=event_id,
            user_id=user["id"],
        )

    return {
        "ok": True,
        "approved_now": approved,
        "status": status,
    }


@app.post("/api/events/{event_id}/completion/export", dependencies=[Depends(require_user)])
def complete_event_and_export_xmp(event_id: str, user=Depends(require_user)):
    try:
        with db() as conn:
            export = build_event_xmp_export(
                conn,
                data_dir=DATA_DIR,
                ai_profiles_dir=AI_PROFILES_DIR,
                event_id=event_id,
                user_id=user["id"],
            )
            status = event_completion_status(
                conn,
                event_id=event_id,
                user_id=user["id"],
            )
    except KeyError:
        raise HTTPException(404, "האירוע לא נמצא")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {
        "ok": True,
        "export_format": EXPORT_FORMAT,
        "export": export,
        "status": status,
    }


@app.get("/api/events/{event_id}/completion/export/{export_id}/download", dependencies=[Depends(require_user)])
def download_event_xmp_export(event_id: str, export_id: str, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM event_exports
            WHERE id=? AND event_id=? AND user_id=?
            """,
            (export_id, event_id, user["id"]),
        ).fetchone()
    if not row:
        raise HTTPException(404, "קובץ הייצוא לא נמצא")

    path = DATA_DIR / row["file_path"]
    if not path.exists():
        raise HTTPException(404, "קובץ ה-ZIP אינו קיים יותר במחשב")

    return FileResponse(
        path,
        media_type="application/zip",
        filename=row["file_name"],
    )


@app.delete("/api/events/{event_id}", dependencies=[Depends(require_user)])
def delete_event(event_id: str, keep_learning: bool = True):
    """
    Permanently deletes the event and every photo-related database record.

    keep_learning=True preserves only the photographer-style learning signal:
    verdict + AI recipe + photographer recipe.
    No image, preview, EXIF, embedding, render, analysis, or event metadata
    is retained in the learning archive.
    """
    archived_count = 0
    deleted_photo_count = 0

    with db() as conn:
        event = conn.execute(
            "SELECT id FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        deleted_photo_count = conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE event_id = ?",
            (event_id,),
        ).fetchone()["c"]

        if keep_learning:
            feedback_rows = conn.execute(
                """
                SELECT
                    f.id,
                    f.verdict,
                    f.ai_recipe_json,
                    f.photographer_recipe_json,
                    f.created_at
                FROM feedback f
                INNER JOIN photos p ON p.id = f.photo_id
                WHERE p.event_id = ?
                  AND f.verdict IN (
                      'approved',
                      'selected_default',
                      'selected_final',
                      'corrected',
                      'מושלם'
                  )
                """,
                (event_id,),
            ).fetchall()

            archived_at = utc_now()

            for row in feedback_rows:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO style_learning_archive
                    (
                        id,
                        source_event_id,
                        source_feedback_id,
                        verdict,
                        ai_recipe_json,
                        photographer_recipe_json,
                        created_at,
                        archived_at,
                        user_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        event_id,
                        row["id"],
                        row["verdict"],
                        row["ai_recipe_json"],
                        row["photographer_recipe_json"],
                        row["created_at"],
                        archived_at,
                        event["user_id"],
                    ),
                )
                archived_count += 1

        # Foreign-key cascades remove photos, feedback, analyses, renders
        # and vision embeddings associated with this event.
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))

    event_root = EVENTS_DIR / event_id
    files_deleted = True
    filesystem_warning = None

    if event_root.exists():
        try:
            shutil.rmtree(event_root)
        except Exception as exc:
            files_deleted = False
            filesystem_warning = str(exc)

    return {
        "ok": True,
        "event_id": event_id,
        "deleted_photos": deleted_photo_count,
        "keep_learning": keep_learning,
        "learning_samples_preserved": archived_count,
        "database_deleted": True,
        "files_deleted": files_deleted,
        "filesystem_warning": filesystem_warning,
    }


@app.post("/api/events/{event_id}/photos", dependencies=[Depends(require_user)])
async def upload_photos(
    event_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
):
    with db() as conn:
        event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

    # Production V1 is RAW-only. Reject the whole batch before writing a single
    # file so a photographer cannot accidentally create a mixed RAW/JPG event.
    invalid_names = []
    for item in files:
        candidate = clean_filename(item.filename or "photo")
        if Path(candidate).suffix.lower() not in SUPPORTED_RAW:
            invalid_names.append(candidate)
    if invalid_names:
        examples = ", ".join(invalid_names[:5])
        raise HTTPException(
            415,
            f"ProGrapher V1 עורך אירועי RAW בלבד. נמצאו קבצים שאינם RAW: {examples}",
        )

    dirs = event_dirs(event_id)
    uploaded = []

    for item in files:
        original_name = clean_filename(item.filename or "photo")
        photo_id = str(uuid.uuid4())
        stored_name = f"{photo_id}_{original_name}"
        destination = dirs["originals"] / stored_name

        with destination.open("wb") as out:
            while chunk := await item.read(1024 * 1024):
                out.write(chunk)

        file_size = destination.stat().st_size
        digest = sha256_file(destination)

        preview = dirs["previews"] / f"{photo_id}.jpg"
        preview_ok, width, height, photo_status = create_preview(destination, preview)

        original_rel = destination.relative_to(DATA_DIR).as_posix()
        preview_rel = preview.relative_to(DATA_DIR).as_posix() if preview_ok else None

        metadata = extract_photo_metadata(destination, width=width, height=height)
        save_metadata_sidecar(event_id, photo_id, metadata)

        now = utc_now()
        with db() as conn:
            conn.execute(
                """
                INSERT INTO photos
                (id, event_id, original_name, stored_name, original_path, preview_path,
                 edited_path, file_size, sha256, width, height, status,
                 metadata_json, metadata_updated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    photo_id,
                    event_id,
                    original_name,
                    stored_name,
                    original_rel,
                    preview_rel,
                    file_size,
                    digest,
                    width,
                    height,
                    photo_status,
                    json.dumps(metadata, ensure_ascii=False),
                    now,
                    now,
                    now,
                ),
            )

        uploaded.append(
            {
                "id": photo_id,
                "name": original_name,
                "size": file_size,
                "status": photo_status,
                "preview_url": url_for_media(request, preview_rel) if preview_rel else None,
            }
        )

    with db() as conn:
        conn.execute(
            "UPDATE events SET status = ?, updated_at = ? WHERE id = ?",
            ("מוכן לניתוח", utc_now(), event_id),
        )

    return {"count": len(uploaded), "photos": uploaded}

@app.get("/api/events/{event_id}/photos", dependencies=[Depends(require_user)])
def list_event_photos(event_id: str, request: Request):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE event_id = ? ORDER BY created_at ASC",
            (event_id,),
        ).fetchall()
    return [row_to_photo(request, row) for row in rows]

@app.get("/api/photos/{photo_id}", dependencies=[Depends(require_user)])
def get_photo(photo_id: str, request: Request):
    with db() as conn:
        row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")
    return row_to_photo(request, row)



def classify_exposure(mean_brightness: float) -> tuple[str, float]:
    if mean_brightness < 85:
        return "כהה", 0.45
    if mean_brightness < 110:
        return "כהה מעט", 0.25
    if mean_brightness > 200:
        return "בהירה מאוד", -0.35
    if mean_brightness > 170:
        return "בהירה מעט", -0.18
    return "מאוזנת", 0.0

def classify_color(warmth_score: float) -> tuple[str, int]:
    if warmth_score > 18:
        return "חמה", -6
    if warmth_score < -18:
        return "קרה", 8
    return "מאוזנת", 0

def analyze_image_from_preview(preview_path: Path) -> dict:
    with Image.open(preview_path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        sample = img.copy()
        sample.thumbnail((900, 900))
        gray = sample.convert("L")
        stat_gray = ImageStat.Stat(gray)
        mean_brightness = float(stat_gray.mean[0])
        contrast_std = float(stat_gray.stddev[0])

        hist = gray.histogram()
        total = max(1, sum(hist))
        shadow_clip = round((sum(hist[:5]) / total) * 100, 2)
        highlight_clip = round((sum(hist[251:]) / total) * 100, 2)

        rgb_stat = ImageStat.Stat(sample)
        mean_r, mean_g, mean_b = [float(x) for x in rgb_stat.mean]
        warmth_score = round(mean_r - mean_b, 2)

        tiny = sample.copy()
        tiny.thumbnail((180, 180))
        pixels = list(tiny.getdata())
        saturation_sum = 0.0
        for r, g, b in pixels:
            _, s, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            saturation_sum += s
        mean_saturation = round((saturation_sum / max(1, len(pixels))) * 100, 2)

    exposure_state, exposure_value = classify_exposure(mean_brightness)
    color_state, temperature_value = classify_color(warmth_score)

    highlights = 0
    whites = 0
    if highlight_clip > 2.0:
        highlights -= 35
        whites -= 15
    elif highlight_clip > 0.5:
        highlights -= 18
        whites -= 8

    shadows = 0
    blacks = 0
    if shadow_clip > 2.0:
        shadows += 28
        blacks += 10
    elif shadow_clip > 0.5:
        shadows += 15
        blacks += 5

    contrast = 0
    clarity = 0
    if contrast_std < 38:
        contrast += 18
        clarity += 10
    elif contrast_std < 50:
        contrast += 10
        clarity += 6
    elif contrast_std > 78:
        contrast -= 6

    vibrance = 0
    if mean_saturation < 23:
        vibrance = 22
    elif mean_saturation < 35:
        vibrance = 12
    elif mean_saturation > 68:
        vibrance = -6

    dynamic_range_state = "שומרת פרטים יפה"
    if highlight_clip > 2.0 and shadow_clip > 2.0:
        dynamic_range_state = "יש עומס גם בבהירים וגם בצללים"
    elif highlight_clip > 2.0:
        dynamic_range_state = "יש איבוד פרטים בבהירים"
    elif shadow_clip > 2.0:
        dynamic_range_state = "יש איבוד פרטים בצללים"

    summary_parts = [
        f"התמונה נראית {exposure_state}.",
        f"הצבע הכללי {color_state}.",
        f"{dynamic_range_state}.",
    ]
    if mean_saturation < 25:
        summary_parts.append("הצבעים מעט שטוחים ולכן כדאי חיזוק עדין.")
    elif mean_saturation > 70:
        summary_parts.append("הצבעים כבר חזקים ולכן כדאי להיזהר לא להגזים.")

    recipe = {
        "exposure": round(exposure_value, 2),
        "highlights": highlights,
        "shadows": shadows,
        "whites": whites,
        "blacks": blacks,
        "contrast": contrast,
        "temperature": temperature_value,
        "vibrance": vibrance,
        "clarity": clarity,
    }

    confidence = 78
    if highlight_clip < 1 and shadow_clip < 1:
        confidence += 6
    if 100 <= mean_brightness <= 170:
        confidence += 4
    confidence = min(confidence, 92)

    return {
        "metrics": {
            "mean_brightness": round(mean_brightness, 2),
            "contrast_std": round(contrast_std, 2),
            "highlight_clip_percent": highlight_clip,
            "shadow_clip_percent": shadow_clip,
            "mean_saturation_percent": mean_saturation,
            "warmth_score": warmth_score,
        },
        "assessment": {
            "exposure_state": exposure_state,
            "color_state": color_state,
            "dynamic_range_state": dynamic_range_state,
            "readiness": "מוכנה לניתוח עריכה ראשוני",
            "summary_he": " ".join(summary_parts),
            "confidence_percent": confidence,
            "analysis_source": "preview",
        },
        "recipe": recipe,
    }

def latest_analysis_for_photo(photo_id: str):
    with db() as conn:
        return conn.execute(
            """
            SELECT * FROM photo_analyses
            WHERE photo_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()


def _clamp_channel(v: float) -> int:
    return max(0, min(255, int(round(v))))

def apply_temperature_adjustment(img: Image.Image, amount: float) -> Image.Image:
    if amount == 0:
        return img
    r, g, b = img.split()
    strength = max(-100.0, min(100.0, float(amount)))
    red_shift = strength * 0.9
    blue_shift = strength * -0.9
    r = r.point(lambda x: _clamp_channel(x + red_shift))
    b = b.point(lambda x: _clamp_channel(x + blue_shift))
    return Image.merge("RGB", (r, g, b))

def apply_local_tone_adjustments(img: Image.Image, shadows: float, highlights: float, blacks: float, whites: float) -> Image.Image:
    gray = ImageOps.grayscale(img)

    if shadows != 0:
        # Stronger on darker pixels
        mask = gray.point(lambda p: int(((255 - p) / 255.0) ** 1.4 * min(abs(shadows), 100)))
        adjusted = ImageEnhance.Brightness(img).enhance(max(0.35, 1.0 + shadows / 120.0))
        img = Image.composite(adjusted, img, mask)

    if highlights != 0:
        # Stronger on brighter pixels
        mask = gray.point(lambda p: int((p / 255.0) ** 1.5 * min(abs(highlights), 100)))
        adjusted = ImageEnhance.Brightness(img).enhance(max(0.35, 1.0 + highlights / 140.0))
        img = Image.composite(adjusted, img, mask)

    if blacks != 0:
        mask = gray.point(lambda p: int(((255 - p) / 255.0) ** 2.2 * min(abs(blacks), 100)))
        adjusted = ImageEnhance.Contrast(img).enhance(max(0.4, 1.0 + blacks / 100.0))
        img = Image.composite(adjusted, img, mask)

    if whites != 0:
        mask = gray.point(lambda p: int((p / 255.0) ** 2.2 * min(abs(whites), 100)))
        adjusted = ImageEnhance.Contrast(img).enhance(max(0.4, 1.0 + whites / 110.0))
        img = Image.composite(adjusted, img, mask)

    return img


RECIPE_LIMITS = {
    "exposure": (-3.0, 3.0),
    "highlights": (-100.0, 100.0),
    "shadows": (-100.0, 100.0),
    "whites": (-100.0, 100.0),
    "blacks": (-100.0, 100.0),
    "contrast": (-100.0, 100.0),
    "temperature": (-100.0, 100.0),
    "vibrance": (-100.0, 100.0),
    "clarity": (-100.0, 100.0),
}

def sanitize_recipe(recipe: dict) -> dict:
    clean = {}
    for key, (min_value, max_value) in RECIPE_LIMITS.items():
        try:
            value = float(recipe.get(key, 0))
        except (TypeError, ValueError):
            value = 0.0
        value = max(min_value, min(max_value, value))
        # Keep Exposure fractional, others cleaner as whole values.
        clean[key] = round(value, 2) if key == "exposure" else round(value, 1)
    return clean

STYLE_LABELS_HE = {
    "exposure": "חשיפה",
    "highlights": "אזורים בהירים",
    "shadows": "צללים",
    "whites": "לבנים",
    "blacks": "שחורים",
    "contrast": "ניגודיות",
    "temperature": "טמפרטורה",
    "vibrance": "חיוניות",
    "clarity": "בהירות מקומית",
}

STYLE_ACCEPTED_VERDICTS = {
    "approved",
    "selected_default",
    "selected_final",
    "מושלם",
}

def _safe_json_dict(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None

def calculate_style_dna(user_id: Optional[str] = None) -> dict:
    """
    Style DNA V1 is intentionally simple and explainable.

    Each completed feedback decision becomes a learning sample:
    - approved/default/final = zero correction (AI recipe was accepted)
    - corrected = photographer_recipe - ai_recipe

    The average delta is shrunk while the dataset is small so that one
    correction cannot dramatically change future photos.
    """
    with db() as conn:
        if user_id:
            rows=conn.execute("""SELECT verdict,ai_recipe_json,photographer_recipe_json,created_at FROM (SELECT f.verdict,f.ai_recipe_json,f.photographer_recipe_json,f.created_at FROM feedback f INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=? UNION ALL SELECT verdict,ai_recipe_json,photographer_recipe_json,created_at FROM style_learning_archive WHERE user_id=?) ORDER BY created_at ASC""",(user_id,user_id)).fetchall()
        else:
            rows=conn.execute("""SELECT verdict,ai_recipe_json,photographer_recipe_json,created_at FROM (SELECT verdict,ai_recipe_json,photographer_recipe_json,created_at FROM feedback UNION ALL SELECT verdict,ai_recipe_json,photographer_recipe_json,created_at FROM style_learning_archive) ORDER BY created_at ASC""").fetchall()

    delta_samples: list[dict[str, float]] = []
    correction_count = 0
    approval_count = 0
    default_count = 0

    for row in rows:
        verdict = str(row["verdict"] or "")
        ai_recipe = _safe_json_dict(row["ai_recipe_json"])
        photographer_recipe = _safe_json_dict(row["photographer_recipe_json"])

        if not ai_recipe:
            continue

        ai_recipe = sanitize_recipe(ai_recipe)

        if verdict == "corrected" and photographer_recipe:
            photographer_recipe = sanitize_recipe(photographer_recipe)
            delta = {
                key: float(photographer_recipe[key]) - float(ai_recipe[key])
                for key in RECIPE_LIMITS
            }
            delta_samples.append(delta)
            correction_count += 1
            continue

        if verdict in STYLE_ACCEPTED_VERDICTS:
            delta_samples.append({key: 0.0 for key in RECIPE_LIMITS})
            approval_count += 1
            if verdict in {"selected_default", "selected_final"}:
                default_count += 1

    sample_count = len(delta_samples)

    if sample_count == 0:
        return {
            "version": 1,
            "sample_count": 0,
            "correction_count": 0,
            "approval_count": 0,
            "default_count": 0,
            "confidence_percent": 0.0,
            "learning_strength_percent": 0.0,
            "bias": {key: 0 for key in RECIPE_LIMITS},
            "raw_average_delta": {key: 0 for key in RECIPE_LIMITS},
            "average_abs_delta": {key: 0 for key in RECIPE_LIMITS},
            "top_adjustments": [],
            "status_he": "עדיין אין מספיק משוב כדי ללמוד את הסגנון.",
        }

    # Gradual learning: 1 sample = 12.5% influence, 8+ samples = full influence.
    learning_strength = min(1.0, sample_count / 8.0)

    raw_average: dict[str, float] = {}
    average_abs: dict[str, float] = {}
    bias: dict[str, float] = {}

    for key in RECIPE_LIMITS:
        values = [sample[key] for sample in delta_samples]
        avg = sum(values) / len(values)
        avg_abs = sum(abs(v) for v in values) / len(values)

        learned = avg * learning_strength

        raw_average[key] = round(avg, 2)
        average_abs[key] = round(avg_abs, 2)
        bias[key] = round(learned, 2) if key == "exposure" else round(learned, 1)

    confidence = min(
        95.0,
        round(100.0 * (1.0 - math.exp(-sample_count / 10.0)), 1),
    )

    top_adjustments = [
        {
            "key": key,
            "label": STYLE_LABELS_HE[key],
            "bias": bias[key],
            "raw_average_delta": raw_average[key],
        }
        for key in RECIPE_LIMITS
        if abs(float(bias[key])) > 0.001
    ]
    top_adjustments.sort(key=lambda item: abs(float(item["bias"])), reverse=True)

    if sample_count < 3:
        status_he = "הלמידה התחילה. ההשפעה עדיין עדינה כדי לא ללמוד מהר מדי ממעט תמונות."
    elif sample_count < 8:
        status_he = "נבנה כיוון סגנון ראשוני. כל החלטה נוספת תחזק את הדיוק."
    elif sample_count < 20:
        status_he = "מפת הסגנון כבר משפיעה באופן מלא על מתכוני עריכה חדשים."
    else:
        status_he = "נאסף בסיס משוב משמעותי ומפת הסגנון פעילה באופן מלא."

    return {
        "version": 1,
        "sample_count": sample_count,
        "correction_count": correction_count,
        "approval_count": approval_count,
        "default_count": default_count,
        "confidence_percent": confidence,
        "learning_strength_percent": round(learning_strength * 100.0, 1),
        "bias": bias,
        "raw_average_delta": raw_average,
        "average_abs_delta": average_abs,
        "top_adjustments": top_adjustments[:5],
        "status_he": status_he,
    }

def apply_style_dna(base_recipe: dict, dna: dict) -> dict:
    clean_base = sanitize_recipe(base_recipe)
    bias = dna.get("bias") or {}

    personalized = {}
    for key in RECIPE_LIMITS:
        personalized[key] = float(clean_base[key]) + float(bias.get(key, 0) or 0)

    return sanitize_recipe(personalized)

def render_recipe_on_preview(preview_path: Path, recipe: dict, destination: Path) -> tuple[int, int]:
    with Image.open(preview_path) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")

        exposure = float(recipe.get("exposure", 0))
        contrast = float(recipe.get("contrast", 0))
        vibrance = float(recipe.get("vibrance", 0))
        temperature = float(recipe.get("temperature", 0))
        clarity = float(recipe.get("clarity", 0))
        shadows = float(recipe.get("shadows", 0))
        highlights = float(recipe.get("highlights", 0))
        whites = float(recipe.get("whites", 0))
        blacks = float(recipe.get("blacks", 0))

        # Global adjustments
        if exposure != 0:
            img = ImageEnhance.Brightness(img).enhance(max(0.3, 1.0 + (exposure * 0.42)))

        if contrast != 0:
            img = ImageEnhance.Contrast(img).enhance(max(0.3, 1.0 + contrast / 85.0))

        if vibrance != 0:
            img = ImageEnhance.Color(img).enhance(max(0.2, 1.0 + vibrance / 80.0))

        if temperature != 0:
            img = apply_temperature_adjustment(img, temperature)

        # Local tonal tweaks
        img = apply_local_tone_adjustments(
            img,
            shadows=shadows,
            highlights=highlights,
            blacks=blacks,
            whites=whites,
        )

        if clarity > 0:
            img = img.filter(
                ImageFilter.UnsharpMask(
                    radius=1.6,
                    percent=min(220, int(clarity * 12)),
                    threshold=2,
                )
            )
        elif clarity < 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=min(2.0, abs(clarity) / 12.0)))

        destination.parent.mkdir(parents=True, exist_ok=True)
        img.save(destination, format="JPEG", quality=94, optimize=True)
        return img.size


def latest_feedback_for_photo(photo_id: str):
    with db() as conn:
        return conn.execute(
            """
            SELECT * FROM feedback
            WHERE photo_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()

def latest_render_for_photo(photo_id: str):
    with db() as conn:
        return conn.execute(
            """
            SELECT * FROM photo_renders
            WHERE photo_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()

@app.get("/api/events/{event_id}/gallery", dependencies=[Depends(require_user)])
def event_gallery(event_id: str, request: Request):
    with db() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        photos = conn.execute(
            "SELECT * FROM photos WHERE event_id = ? ORDER BY created_at ASC",
            (event_id,),
        ).fetchall()

    output_photos = [row_to_photo(request, row, include_metadata=True) for row in photos]

    with db() as conn:
        active_registry = get_default_active_profile(
            conn,
            user_id=dict(event).get("user_id"),
        )
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        predictions = (
            current_prediction_map(
                conn,
                photo_ids=[p["id"] for p in output_photos],
                profile_version_id=active_version_id,
            )
            if active_version_id
            else {}
        )

    for photo in output_photos:
        photo["latest_ai_prediction"] = predictions.get(photo["id"])

    raw_count = sum(1 for p in output_photos if p.get("is_raw"))
    ready_count = sum(1 for p in output_photos if p.get("preview_url"))

    return {
        "event": dict(event),
        "summary": {
            "photo_count": len(output_photos),
            "raw_count": raw_count,
            "preview_count": ready_count,
            "ai_prediction_count": len(predictions),
            "total_bytes": sum(int(p.get("file_size") or 0) for p in output_photos),
        },
        "photos": output_photos,
    }

@app.get("/api/photos/{photo_id}/details", dependencies=[Depends(require_user)])
def photo_details(photo_id: str, request: Request):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    output = row_to_photo(request, row, include_metadata=True)
    latest = latest_analysis_for_photo(photo_id)
    output["latest_analysis"] = dict(latest) if latest else None
    latest_render = latest_render_for_photo(photo_id)
    output["latest_render"] = dict(latest_render) if latest_render else None
    latest_feedback = latest_feedback_for_photo(photo_id)
    output["latest_feedback"] = dict(latest_feedback) if latest_feedback else None
    with db() as conn:
        active_registry = get_default_active_profile(
            conn,
            user_id=owner_user_id_for_photo(photo_id),
        )
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        output["latest_ai_prediction"] = latest_prediction_for_photo(
            conn,
            photo_id=photo_id,
            profile_version_id=active_version_id,
        )
        output["active_ai_profile"] = _active_profile_summary(active_registry)
        prediction_id = (
            output["latest_ai_prediction"]["id"]
            if output.get("latest_ai_prediction")
            else None
        )
        ai_render = latest_ai_preview_render(
            conn,
            photo_id=photo_id,
            prediction_id=prediction_id,
        )
        output["latest_ai_preview_render"] = (
            _production_render_public(request, ai_render)
            if ai_render
            else None
        )
        learning_decision = latest_learning_for_photo(
            conn,
            photo_id=photo_id,
            profile_version_id=active_version_id,
        )
        if learning_decision and learning_decision.get("final_render_path"):
            final_path = DATA_DIR / learning_decision["final_render_path"]
            learning_decision["final_render_url"] = (
                url_for_media(request, learning_decision["final_render_path"])
                if final_path.exists()
                else None
            )
        output["latest_ai_learning_decision"] = learning_decision

    latest_brain = latest_brain_vision_for_photo(photo_id)
    if latest_brain:
        brain_row = dict(latest_brain)
        output["latest_brain"] = {
            "id": brain_row["id"],
            "model_name": brain_row["model_name"],
            "device": brain_row["device"],
            "embedding_dimensions": brain_row["embedding_dimensions"],
            "created_at": brain_row["created_at"],
            **json.loads(brain_row["semantics_json"]),
        }
    else:
        output["latest_brain"] = None
    return output



def latest_brain_vision_for_photo(photo_id: str):
    with db() as conn:
        return conn.execute(
            """
            SELECT * FROM photo_brain_vision
            WHERE photo_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (photo_id,),
        ).fetchone()


def brain_training_dataset_stats(user_id: Optional[str] = None) -> dict:
    with db() as conn:
        if user_id:
            total=conn.execute("SELECT COUNT(*) c FROM photos p INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=?",(user_id,)).fetchone()["c"]
            embedded=conn.execute("SELECT COUNT(DISTINCT v.photo_id) c FROM photo_brain_vision v INNER JOIN photos p ON p.id=v.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=?",(user_id,)).fetchone()["c"]
            feedback=conn.execute("SELECT COUNT(*) c FROM feedback f INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=?",(user_id,)).fetchone()["c"]
            paired=conn.execute("SELECT COUNT(DISTINCT f.photo_id) c FROM feedback f INNER JOIN photo_brain_vision v ON v.photo_id=f.photo_id INNER JOIN photos p ON p.id=f.photo_id INNER JOIN events e ON e.id=p.event_id WHERE e.user_id=?",(user_id,)).fetchone()["c"]
        else:
            total=conn.execute("SELECT COUNT(*) c FROM photos").fetchone()["c"]; embedded=conn.execute("SELECT COUNT(DISTINCT photo_id) c FROM photo_brain_vision").fetchone()["c"]; feedback=conn.execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"]; paired=conn.execute("SELECT COUNT(DISTINCT f.photo_id) c FROM feedback f INNER JOIN photo_brain_vision v ON v.photo_id=f.photo_id").fetchone()["c"]
    return {"total_photos":total,"embedded_photos":embedded,"feedback_rows":feedback,"training_ready_samples":paired,"coverage_percent":round((embedded/total)*100.0,1) if total else 0.0}



@app.on_event("startup")
def recover_profile_ai_jobs():
    # Vision jobs are resumable because feature JSONL files are append-only and
    # processed sample IDs are detected on restart. Training is restarted by
    # user action so a half-built model is never silently trusted.
    with db() as conn:
        stuck_vision = conn.execute(
            "SELECT * FROM lightroom_vision_jobs WHERE status IN ('queued','building') ORDER BY created_at ASC"
        ).fetchall()
        stuck_training = conn.execute(
            "SELECT * FROM lightroom_training_runs WHERE status IN ('queued','building')"
        ).fetchall()
        stuck_training_v2 = conn.execute(
            "SELECT * FROM lightroom_training_v2_runs WHERE status IN ('queued','building')"
        ).fetchall()

        for run in stuck_training:
            conn.execute(
                "UPDATE lightroom_training_runs SET status='failed',stage='failed',progress_percent=100,error=?,updated_at=? WHERE id=?",
                ("Local Engine restarted during training. Start training again to create a clean model.", utc_now(), run["id"]),
            )

        for run in stuck_training_v2:
            conn.execute(
                "UPDATE lightroom_training_v2_runs SET status='failed',stage='failed',progress_percent=100,error=?,updated_at=? WHERE id=?",
                ("Local Engine restarted during V2 training. Start V2 training again to create a clean model.", utc_now(), run["id"]),
            )

        vision_rows = [dict(row) for row in stuck_vision]

    for row in vision_rows:
        _update_vision_job(
            row["id"],
            status="failed",
            stage="failed",
            progress=100,
            error="Local Engine restarted; Vision preprocessing resumed in a new job.",
        )
        _start_vision_job(row["profile_import_id"], row["dataset_build_id"], row["user_id"])


@app.get("/api/brain/status", dependencies=[Depends(require_user)])
def get_brain_status(user=Depends(require_user)):
    status=brain_status(); status["dataset"]=brain_training_dataset_stats(user["id"]); return status


@app.post("/api/brain/warmup", dependencies=[Depends(require_user)])
def warmup_brain(user=Depends(require_user)):
    try: result=get_brain().warmup()
    except BrainUnavailableError as exc: raise HTTPException(503,str(exc)) from exc
    result["dataset"]=brain_training_dataset_stats(user["id"]); return result


@app.post(
    "/api/photos/{photo_id}/brain/analyze",
    dependencies=[Depends(require_user)],
)
def analyze_photo_with_brain(photo_id: str):
    return save_brain_analysis_for_photo(photo_id)


@app.get(
    "/api/photos/{photo_id}/brain/latest",
    dependencies=[Depends(require_user)],
)
def latest_photo_brain_analysis(photo_id: str):
    row = latest_brain_vision_for_photo(photo_id)

    if not row:
        return {
            "ok": True,
            "exists": False,
            "analysis": None,
        }

    item = dict(row)
    semantics = json.loads(item["semantics_json"])

    return {
        "ok": True,
        "exists": True,
        "analysis": {
            "id": item["id"],
            "photo_id": item["photo_id"],
            "model_name": item["model_name"],
            "device": item["device"],
            "embedding_dimensions": item["embedding_dimensions"],
            "created_at": item["created_at"],
            **semantics,
        },
    }


def save_brain_analysis_for_photo(photo_id: str) -> dict:
    """
    Analyze the ORIGINAL source using the exact same Vision preprocessing
    contract used to create the FiveK training embeddings.

    This avoids a silent train/inference mismatch where production used the
    website JPEG preview while training used RAW embedded previews / rawpy.
    """
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    item = dict(row)
    original_path = DATA_DIR / item["original_path"]
    if not original_path.exists():
        raise HTTPException(404, "קובץ המקור לא נמצא")

    image = None
    try:
        image = load_vision_image(original_path)
        result = get_brain().analyze_image(image)
        feature_metadata = extract_training_metadata(original_path)
    except BrainUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            500,
            f"ניתוח ה-AI המקומי נכשל: {exc}",
        ) from exc
    finally:
        try:
            if image is not None:
                image.close()
        except Exception:
            pass

    if not feature_metadata.get("width"):
        feature_metadata["width"] = float(item.get("width") or 0)
    if not feature_metadata.get("height"):
        feature_metadata["height"] = float(item.get("height") or 0)

    brain_id = str(uuid.uuid4())
    created_at = utc_now()

    semantics = {
        "groups": result["groups"],
        "top": result["top"],
        "source": result["source"],
        "preprocessing_contract": VISION_PREPROCESSING_CONTRACT,
        "feature_metadata": feature_metadata,
    }

    with db() as conn:
        conn.execute(
            """
            INSERT INTO photo_brain_vision
            (
                id,
                photo_id,
                model_name,
                device,
                embedding_dimensions,
                embedding_json,
                semantics_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brain_id,
                photo_id,
                result["model_name"],
                result["device"],
                result["embedding_dimensions"],
                json.dumps(result["embedding"]),
                json.dumps(semantics, ensure_ascii=False),
                created_at,
            ),
        )

    return {
        "ok": True,
        "brain_analysis_id": brain_id,
        "photo_id": photo_id,
        "created_at": created_at,
        "model_name": result["model_name"],
        "device": result["device"],
        "embedding_dimensions": result["embedding_dimensions"],
        **semantics,
    }


def latest_production_brain_vision_for_photo(photo_id: str):
    """
    Return only a Vision row built with the production/training-compatible
    preprocessing contract. Old preview-based rows are intentionally ignored.
    """
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM photo_brain_vision
            WHERE photo_id=?
            ORDER BY created_at DESC
            """,
            (photo_id,),
        ).fetchall()

    for row in rows:
        if brain_matches_production_contract(row):
            return row
    return None


def ensure_production_brain_vision_for_photo(photo_id: str):
    row = latest_production_brain_vision_for_photo(photo_id)
    if row:
        return row, True

    save_brain_analysis_for_photo(photo_id)
    row = latest_production_brain_vision_for_photo(photo_id)
    if not row:
        raise RuntimeError("Production Vision analysis was not saved.")
    return row, False


def event_brain_coverage(event_id: str) -> dict:
    with db() as conn:
        event_row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if not event_row:
            raise HTTPException(404, "האירוע לא נמצא")

        total = conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE event_id = ?",
            (event_id,),
        ).fetchone()["c"]

        with_preview = conn.execute(
            """
            SELECT COUNT(*) c
            FROM photos
            WHERE event_id = ?
              AND preview_path IS NOT NULL
              AND preview_path != ''
            """,
            (event_id,),
        ).fetchone()["c"]

        embedded = conn.execute(
            """
            SELECT COUNT(DISTINCT p.id) c
            FROM photos p
            INNER JOIN photo_brain_vision v ON v.photo_id = p.id
            WHERE p.event_id = ?
            """,
            (event_id,),
        ).fetchone()["c"]

    return {
        "event_id": event_id,
        "total_photos": total,
        "photos_with_preview": with_preview,
        "embedded_photos": embedded,
        "missing_embeddings": max(0, with_preview - embedded),
        "coverage_percent": round((embedded / with_preview) * 100.0, 1) if with_preview else 0.0,
    }


@app.get(
    "/api/events/{event_id}/brain/coverage",
    dependencies=[Depends(require_user)],
)
def get_event_brain_coverage(event_id: str):
    return event_brain_coverage(event_id)


@app.post(
    "/api/events/{event_id}/brain/analyze-all",
    dependencies=[Depends(require_user)],
)
def analyze_event_with_brain(event_id: str):
    coverage_before = event_brain_coverage(event_id)

    with db() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM photos
            WHERE event_id = ?
              AND preview_path IS NOT NULL
              AND preview_path != ''
            ORDER BY created_at ASC
            """,
            (event_id,),
        ).fetchall()

    analyzed = []
    failed = []

    for row in rows:
        photo_id = row["id"]
        try:
            result = save_brain_analysis_for_photo(photo_id)
            analyzed.append({
                "photo_id": photo_id,
                "brain_analysis_id": result["brain_analysis_id"],
            })
        except Exception as exc:
            failed.append({
                "photo_id": photo_id,
                "error": str(exc),
            })

    coverage_after = event_brain_coverage(event_id)

    return {
        "ok": True,
        "mode": "all",
        "event_id": event_id,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "analyzed_count": len(analyzed),
        "failed_count": len(failed),
        "analyzed": analyzed,
        "failed": failed,
    }


@app.post(
    "/api/events/{event_id}/brain/analyze-missing",
    dependencies=[Depends(require_user)],
)
def analyze_missing_event_photos_with_brain(event_id: str):
    coverage_before = event_brain_coverage(event_id)

    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.id
            FROM photos p
            LEFT JOIN (
                SELECT photo_id, MAX(created_at) AS max_created
                FROM photo_brain_vision
                GROUP BY photo_id
            ) v ON v.photo_id = p.id
            WHERE p.event_id = ?
              AND p.preview_path IS NOT NULL
              AND p.preview_path != ''
              AND v.photo_id IS NULL
            ORDER BY p.created_at ASC
            """,
            (event_id,),
        ).fetchall()

    analyzed = []
    failed = []

    for row in rows:
        photo_id = row["id"]
        try:
            result = save_brain_analysis_for_photo(photo_id)
            analyzed.append({
                "photo_id": photo_id,
                "brain_analysis_id": result["brain_analysis_id"],
            })
        except Exception as exc:
            failed.append({
                "photo_id": photo_id,
                "error": str(exc),
            })

    coverage_after = event_brain_coverage(event_id)

    return {
        "ok": True,
        "mode": "missing_only",
        "event_id": event_id,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "analyzed_count": len(analyzed),
        "failed_count": len(failed),
        "analyzed": analyzed,
        "failed": failed,
    }


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a <= 0 or norm_b <= 0:
        return 1.0

    similarity = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return 1.0 - similarity


def _brain_top_label(semantics: dict, group_name: str) -> dict:
    top = (semantics.get("top") or {}).get(group_name)
    if isinstance(top, dict):
        return top
    return {}


def _semantic_signature(semantics: dict) -> str:
    scene = _brain_top_label(semantics, "scene").get("key") or "unknown_scene"
    lighting = _brain_top_label(semantics, "lighting").get("key") or "unknown_light"
    return f"{scene}|{lighting}"


def _semantic_confidence(semantics: dict) -> float:
    score = 0.0
    for group_name in ["scene", "lighting", "people", "framing", "technical"]:
        top = _brain_top_label(semantics, group_name)
        try:
            score += float(top.get("score_percent") or 0.0)
        except Exception:
            pass
    return score


def _latest_feedback_map(photo_ids: list[str]) -> dict[str, dict]:
    if not photo_ids:
        return {}

    placeholders = ",".join("?" for _ in photo_ids)

    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT f.*
            FROM feedback f
            INNER JOIN (
                SELECT photo_id, MAX(created_at) AS max_created
                FROM feedback
                WHERE photo_id IN ({placeholders})
                GROUP BY photo_id
            ) latest
              ON latest.photo_id = f.photo_id
             AND latest.max_created = f.created_at
            """,
            tuple(photo_ids),
        ).fetchall()

    return {row["photo_id"]: dict(row) for row in rows}


def _event_brain_candidates(event_id: str, request: Request) -> tuple[dict, list[dict]]:
    with db() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        rows = conn.execute(
            """
            SELECT
                p.*,
                v.model_name AS brain_model_name,
                v.device AS brain_device,
                v.embedding_json AS brain_embedding_json,
                v.semantics_json AS brain_semantics_json,
                v.created_at AS brain_created_at
            FROM photos p
            INNER JOIN photo_brain_vision v
                ON v.photo_id = p.id
            INNER JOIN (
                SELECT photo_id, MAX(created_at) AS max_created
                FROM photo_brain_vision
                GROUP BY photo_id
            ) latest
                ON latest.photo_id = v.photo_id
               AND latest.max_created = v.created_at
            WHERE p.event_id = ?
              AND p.preview_path IS NOT NULL
              AND p.preview_path != ''
            ORDER BY p.created_at ASC
            """,
            (event_id,),
        ).fetchall()

    candidates = []
    for row in rows:
        raw = dict(row)
        try:
            embedding = json.loads(raw.get("brain_embedding_json") or "[]")
        except Exception:
            embedding = []

        try:
            semantics = json.loads(raw.get("brain_semantics_json") or "{}")
        except Exception:
            semantics = {}

        if not embedding:
            continue

        photo_data = row_to_photo(request, row, include_metadata=True)
        candidates.append({
            "photo": photo_data,
            "embedding": [float(x) for x in embedding],
            "semantics": semantics,
            "signature": _semantic_signature(semantics),
            "semantic_confidence": _semantic_confidence(semantics),
            "brain_model_name": raw.get("brain_model_name"),
            "brain_device": raw.get("brain_device"),
            "brain_created_at": raw.get("brain_created_at"),
        })

    return dict(event), candidates


def _farthest_selection(
    candidates: list[dict],
    count: int,
) -> list[tuple[dict, float, str]]:
    if not candidates:
        return []

    count = max(1, min(count, len(candidates)))

    # First create semantic representatives for scene+lighting combinations.
    buckets: dict[str, list[dict]] = {}
    for candidate in candidates:
        buckets.setdefault(candidate["signature"], []).append(candidate)

    representatives = []
    for signature in sorted(buckets):
        bucket = buckets[signature]
        bucket.sort(
            key=lambda item: (
                -float(item["semantic_confidence"]),
                str(item["photo"]["id"]),
            )
        )
        representatives.append(bucket[0])

    def centroid(items: list[dict]) -> list[float]:
        dims = len(items[0]["embedding"])
        result = [0.0] * dims
        for item in items:
            for idx, value in enumerate(item["embedding"]):
                result[idx] += value
        size = float(len(items))
        return [value / size for value in result]

    selected: list[tuple[dict, float, str]] = []
    selected_ids: set[str] = set()

    # Seed with the representative farthest from the overall visual centroid.
    pool_for_seed = representatives or candidates
    center = centroid(candidates)
    first = max(
        pool_for_seed,
        key=lambda item: (
            _cosine_distance(item["embedding"], center),
            item["semantic_confidence"],
            str(item["photo"]["id"]),
        ),
    )

    selected.append((
        first,
        _cosine_distance(first["embedding"], center),
        "נבחרה כנקודת פתיחה חזותית שונה מהמרכז של האירוע",
    ))
    selected_ids.add(first["photo"]["id"])

    # Prioritize one photo from each semantic bucket when possible.
    semantic_pool = [
        item for item in representatives
        if item["photo"]["id"] not in selected_ids
    ]

    while semantic_pool and len(selected) < count:
        best = None
        best_distance = -1.0

        for item in semantic_pool:
            min_distance = min(
                _cosine_distance(
                    item["embedding"],
                    chosen[0]["embedding"],
                )
                for chosen in selected
            )
            if (
                min_distance > best_distance
                or (
                    math.isclose(min_distance, best_distance)
                    and best is not None
                    and item["semantic_confidence"] > best["semantic_confidence"]
                )
            ):
                best = item
                best_distance = min_distance

        if best is None:
            break

        selected.append((
            best,
            best_distance,
            "נבחרה כדי להוסיף שילוב סצנה ותאורה שונה למאגר האימון",
        ))
        selected_ids.add(best["photo"]["id"])
        semantic_pool = [
            item for item in semantic_pool
            if item["photo"]["id"] not in selected_ids
        ]

    # Fill remaining slots with farthest-point sampling in CLIP space.
    remaining = [
        item for item in candidates
        if item["photo"]["id"] not in selected_ids
    ]

    while remaining and len(selected) < count:
        best = None
        best_distance = -1.0

        for item in remaining:
            min_distance = min(
                _cosine_distance(
                    item["embedding"],
                    chosen[0]["embedding"],
                )
                for chosen in selected
            )

            if (
                min_distance > best_distance
                or (
                    math.isclose(min_distance, best_distance)
                    and best is not None
                    and item["semantic_confidence"] > best["semantic_confidence"]
                )
            ):
                best = item
                best_distance = min_distance

        if best is None:
            break

        selected.append((
            best,
            best_distance,
            "נבחרה כי היא שונה חזותית מהתמונות שכבר נבחרו",
        ))
        selected_ids.add(best["photo"]["id"])
        remaining = [
            item for item in remaining
            if item["photo"]["id"] not in selected_ids
        ]

    return selected


@app.get(
    "/api/events/{event_id}/brain/training-review",
    dependencies=[Depends(require_user)],
)
def training_review_selection(
    event_id: str,
    request: Request,
    count: int = 48,
):
    count = max(8, min(int(count), 80))

    event, candidates = _event_brain_candidates(event_id, request)

    if not candidates:
        raise HTTPException(
            400,
            "אין עדיין תמונות עם ניתוח מוח באירוע הזה. יש להריץ קודם analyze-all.",
        )

    selected = _farthest_selection(candidates, count)

    photo_ids = [item[0]["photo"]["id"] for item in selected]
    feedback_map = _latest_feedback_map(photo_ids)

    output = []

    for rank, (candidate, distance, selection_reason) in enumerate(selected, start=1):
        photo = candidate["photo"]
        semantics = candidate["semantics"]
        feedback = feedback_map.get(photo["id"])

        scene = _brain_top_label(semantics, "scene")
        lighting = _brain_top_label(semantics, "lighting")
        people = _brain_top_label(semantics, "people")
        framing = _brain_top_label(semantics, "framing")
        technical = _brain_top_label(semantics, "technical")

        reviewed = feedback is not None

        output.append({
            "rank": rank,
            "photo_id": photo["id"],
            "original_name": photo["original_name"],
            "preview_url": photo.get("preview_url"),
            "extension": photo.get("extension"),
            "metadata": photo.get("metadata") or {},
            "scene": scene,
            "lighting": lighting,
            "people": people,
            "framing": framing,
            "technical": technical,
            "semantic_signature": candidate["signature"],
            "visual_distance_percent": round(
                max(0.0, min(100.0, distance * 100.0)),
                1,
            ),
            "selection_reason": selection_reason,
            "reviewed": reviewed,
            "feedback_verdict": feedback.get("verdict") if feedback else None,
        })

    reviewed_count = sum(1 for item in output if item["reviewed"])

    signature_count = len({
        candidate["signature"]
        for candidate, _distance, _reason in selected
    })

    return {
        "ok": True,
        "event": event,
        "requested_count": count,
        "analyzed_photos": len(candidates),
        "selected_count": len(output),
        "reviewed_count": reviewed_count,
        "remaining_count": max(0, len(output) - reviewed_count),
        "semantic_combinations": signature_count,
        "method": "semantic_scene_lighting_coverage_plus_clip_farthest_point_sampling",
        "items": output,
    }



@app.get(
    "/api/brain/dataset/stats",
    dependencies=[Depends(require_user)],
)
def brain_dataset_stats_endpoint(user=Depends(require_user)):
    return brain_training_dataset_stats(user["id"])


@app.post(
    "/api/brain/dataset/export",
    dependencies=[Depends(require_user)],
)
def export_brain_training_dataset(user=Depends(require_user)):
    output_dir = DATA_DIR / "ai"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "training_dataset.jsonl"

    with db() as conn:
        vision_rows = conn.execute(
            """
            SELECT v.*
            FROM photo_brain_vision v
            INNER JOIN (SELECT photo_id,MAX(created_at) AS max_created FROM photo_brain_vision GROUP BY photo_id) latest ON latest.photo_id=v.photo_id AND latest.max_created=v.created_at
            INNER JOIN photos p ON p.id=v.photo_id
            INNER JOIN events e ON e.id=p.event_id
            WHERE e.user_id = ?
            ORDER BY v.created_at ASC
            """,
            (user["id"],),
        ).fetchall()

        exported = 0

        with output_path.open("w", encoding="utf-8") as handle:
            for vision_row in vision_rows:
                photo_id = vision_row["photo_id"]

                photo = conn.execute(
                    "SELECT * FROM photos WHERE id = ?",
                    (photo_id,),
                ).fetchone()

                feedback_row = conn.execute(
                    """
                    SELECT * FROM feedback
                    WHERE photo_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (photo_id,),
                ).fetchone()

                analysis_row = conn.execute(
                    """
                    SELECT * FROM photo_analyses
                    WHERE photo_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (photo_id,),
                ).fetchone()

                if not photo:
                    continue

                feedback = dict(feedback_row) if feedback_row else None

                record = {
                    "photo_id": photo_id,
                    "original_name": photo["original_name"],
                    "metadata": _safe_json_dict(
                        photo["metadata_json"]
                    ) or {},
                    "vision_model": vision_row["model_name"],
                    "embedding": json.loads(
                        vision_row["embedding_json"]
                    ),
                    "semantics": json.loads(
                        vision_row["semantics_json"]
                    ),
                    "analysis": (
                        json.loads(analysis_row["analysis_json"])
                        if analysis_row
                        else None
                    ),
                    "feedback": feedback,
                }

                handle.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                    ) + "\n"
                )
                exported += 1

    return {
        "ok": True,
        "records": exported,
        "path": str(output_path),
        "relative_path": "ai/training_dataset.jsonl",
    }



def _active_profile_summary(registry: Optional[dict]) -> Optional[dict]:
    if not registry or not registry.get("active_version"):
        return None
    active = registry["active_version"]
    return {
        "registry_id": registry["id"],
        "name": registry.get("name"),
        "is_default": bool(registry.get("is_default")),
        "version_id": active["id"],
        "version_number": int(active["version_number"]),
        "profile_format": active.get("profile_format"),
        "recipe_contract_version": active.get("recipe_contract_version"),
        "activated_at": active.get("activated_at"),
    }


def _infer_photo_with_active_profile(photo_id: str, user_id: str) -> tuple[dict, bool]:
    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user_id),
        ).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")
        require_production_raw_photo(photo)
        active_registry = get_default_active_profile(conn, user_id=user_id)

    if not active_registry:
        raise HTTPException(
            409,
            "אין AI Profile פעיל. יש להשלים את בניית הסגנון לפני עריכת אירוע.",
        )

    try:
        brain_row, _brain_reused = ensure_production_brain_vision_for_photo(photo_id)

        with db() as conn:
            # Re-read photo inside the prediction transaction.
            photo = conn.execute(
                "SELECT * FROM photos WHERE id=?",
                (photo_id,),
            ).fetchone()
            prediction, reused = predict_photo_with_active_registry(
                conn,
                data_dir=DATA_DIR,
                user_id=user_id,
                photo_row=photo,
                brain_row=brain_row,
                active_registry=active_registry,
            )
            conn.execute(
                """
                UPDATE photos
                SET status=?, updated_at=?
                WHERE id=?
                """,
                ("AI מוכן", utc_now(), photo_id),
            )
        return prediction, reused
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"תחזית ProGrapher נכשלה: {exc}") from exc


def _event_inference_status_payload(event_id: str, user_id: str) -> dict:
    with db() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id=? AND user_id=?",
            (event_id, user_id),
        ).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        active_registry = get_default_active_profile(conn, user_id=user_id)
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        coverage = event_prediction_coverage(
            conn,
            event_id=event_id,
            profile_version_id=active_version_id,
        )
        job = latest_event_inference_job(conn, event_id=event_id)

    return {
        "ok": True,
        "event_id": event_id,
        "active_profile": _active_profile_summary(active_registry),
        "coverage": coverage,
        "job": job,
    }


@app.get("/api/photos/{photo_id}/ai/prediction-latest", dependencies=[Depends(require_user)])
def get_latest_photo_ai_prediction(photo_id: str, user=Depends(require_user)):
    with db() as conn:
        active_registry = get_default_active_profile(conn, user_id=user["id"])
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        prediction = latest_prediction_for_photo(
            conn,
            photo_id=photo_id,
            profile_version_id=active_version_id,
        )
    return {
        "ok": True,
        "exists": prediction is not None,
        "active_profile": _active_profile_summary(active_registry),
        "prediction": prediction,
    }


@app.post("/api/photos/{photo_id}/ai/infer", dependencies=[Depends(require_user)])
def infer_photo_with_active_profile(photo_id: str, user=Depends(require_user)):
    prediction, reused = _infer_photo_with_active_profile(photo_id, user["id"])
    return {
        "ok": True,
        "reused": reused,
        "prediction": prediction,
    }


def _run_event_inference_job(job_id: str, event_id: str, user_id: str):
    processed = 0
    predicted = 0
    reused = 0
    failed = 0
    failures: list[dict] = []

    try:
        with db() as conn:
            active_registry = get_default_active_profile(conn, user_id=user_id)
            if not active_registry:
                raise RuntimeError("No ACTIVE AI Profile.")
            job_row = conn.execute(
                "SELECT * FROM event_ai_inference_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if not job_row:
                return
            # The job must stay pinned to the version selected at creation.
            if job_row["profile_version_id"] != active_registry["active_version"]["id"]:
                raise RuntimeError(
                    "The ACTIVE AI Profile changed before this job started. Start a new job."
                )
            photos = conn.execute(
                """
                SELECT p.id,p.original_name
                FROM photos p
                INNER JOIN events e ON e.id=p.event_id
                WHERE p.event_id=? AND e.user_id=?
                ORDER BY p.created_at ASC
                """,
                (event_id, user_id),
            ).fetchall()
            update_event_inference_job(
                conn,
                job_id=job_id,
                status="running",
                stage="vision_and_prediction",
                progress_percent=0,
                details={
                    "profile_name": active_registry.get("name"),
                    "message": "ProGrapher מנתח את התמונות ומחשב עריכה אישית",
                },
            )

        total = len(photos)
        for index, photo in enumerate(photos, start=1):
            try:
                _prediction, was_reused = _infer_photo_with_active_profile(
                    photo["id"],
                    user_id,
                )
                if was_reused:
                    reused += 1
                else:
                    predicted += 1
            except Exception as exc:
                failed += 1
                failures.append(
                    {
                        "photo_id": photo["id"],
                        "name": photo["original_name"],
                        "error": str(exc)[:300],
                    }
                )

            processed += 1
            pct = int((processed / max(1, total)) * 100)
            with db() as conn:
                update_event_inference_job(
                    conn,
                    job_id=job_id,
                    status="running",
                    stage="vision_and_prediction",
                    progress_percent=min(99, pct),
                    processed_photos=processed,
                    predicted_photos=predicted,
                    reused_photos=reused,
                    failed_photos=failed,
                    details={
                        "message": "ProGrapher עורך את האירוע",
                        "current_photo": photo["original_name"],
                        "failures": failures[-10:],
                    },
                )

        final_status = "completed" if failed == 0 else "completed_with_errors"
        with db() as conn:
            update_event_inference_job(
                conn,
                job_id=job_id,
                status=final_status,
                stage="completed",
                progress_percent=100,
                processed_photos=processed,
                predicted_photos=predicted,
                reused_photos=reused,
                failed_photos=failed,
                details={
                    "message": (
                        "עריכת ה-AI הושלמה"
                        if failed == 0
                        else "עריכת ה-AI הושלמה עם מספר תמונות שנכשלו"
                    ),
                    "failures": failures[-25:],
                },
            )
            conn.execute(
                """
                UPDATE events
                SET status=?, updated_at=?
                WHERE id=? AND user_id=?
                """,
                (
                    "AI מוכן" if failed == 0 else "AI מוכן חלקית",
                    utc_now(),
                    event_id,
                    user_id,
                ),
            )
    except Exception as exc:
        with db() as conn:
            try:
                update_event_inference_job(
                    conn,
                    job_id=job_id,
                    status="failed",
                    stage="failed",
                    progress_percent=100,
                    processed_photos=processed,
                    predicted_photos=predicted,
                    reused_photos=reused,
                    failed_photos=failed,
                    error=str(exc),
                    details={"message": "עריכת האירוע נכשלה"},
                )
            except Exception:
                pass


@app.get("/api/events/{event_id}/ai/inference/status", dependencies=[Depends(require_user)])
def event_ai_inference_status(event_id: str, user=Depends(require_user)):
    return _event_inference_status_payload(event_id, user["id"])


@app.post("/api/events/{event_id}/ai/inference/start", dependencies=[Depends(require_user)])
def start_event_ai_inference(event_id: str, user=Depends(require_user)):
    with db() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id=? AND user_id=?",
            (event_id, user["id"]),
        ).fetchone()
        if not event:
            raise HTTPException(404, "האירוע לא נמצא")

        active_registry = get_default_active_profile(conn, user_id=user["id"])
        if not active_registry:
            raise HTTPException(
                409,
                "אין AI Profile פעיל. יש להשלים את בניית הסגנון לפני עריכת אירוע.",
            )

        running = active_event_inference_job(conn, event_id=event_id)
        if running:
            return {
                "ok": True,
                "started": False,
                "job": running,
                "status": _event_inference_status_payload(event_id, user["id"]),
            }

        total = int(
            conn.execute(
                "SELECT COUNT(*) c FROM photos WHERE event_id=?",
                (event_id,),
            ).fetchone()["c"]
        )
        if total <= 0:
            raise HTTPException(400, "אין תמונות באירוע")

        job = create_event_inference_job(
            conn,
            event_id=event_id,
            user_id=user["id"],
            active_registry=active_registry,
            total_photos=total,
        )

    threading.Thread(
        target=_run_event_inference_job,
        args=(job["id"], event_id, user["id"]),
        daemon=True,
        name=f"prographer-inference-{event_id[:8]}",
    ).start()

    return {
        "ok": True,
        "started": True,
        "job": job,
        "active_profile": _active_profile_summary(active_registry),
    }


@app.on_event("startup")
def recover_interrupted_event_inference_jobs():
    # Prediction rows are immutable and idempotent, so a new job can safely
    # resume later. We never silently trust an interrupted in-memory thread.
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id FROM event_ai_inference_jobs
            WHERE status IN ('queued','running')
            """
        ).fetchall()
        for row in rows:
            update_event_inference_job(
                conn,
                job_id=row["id"],
                status="failed",
                stage="interrupted",
                progress_percent=100,
                error="Local Engine restarted during event inference. Start the event again; completed predictions will be reused.",
                details={
                    "message": "המנוע הופעל מחדש. ניתן להמשיך בבטחה — תחזיות שכבר נשמרו לא יחושבו מחדש."
                },
            )



def _prediction_process_family(prediction: dict) -> str:
    provenance = prediction.get("provenance") or {}
    return infer_process_family(
        prediction.get("recipe") or {},
        provenance.get("process_family"),
    )


def _production_render_public(request: Request, render: Optional[dict]) -> Optional[dict]:
    if not render:
        return None
    item = dict(render)
    item["rendered_url"] = url_for_media(request, item["rendered_path"])
    item["preview_is_approximation"] = True
    return item


def _ensure_prediction_darkroom_render(
    *,
    photo_id: str,
    user_id: str,
    request: Request,
) -> dict:
    prediction, prediction_reused = _infer_photo_with_active_profile(photo_id, user_id)

    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user_id),
        ).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")

        existing = latest_ai_preview_render(
            conn,
            photo_id=photo_id,
            prediction_id=prediction["id"],
        )

    if existing:
        return {
            "prediction": prediction,
            "render": _production_render_public(request, existing),
            "prediction_reused": prediction_reused,
            "render_reused": True,
            "process_family": existing.get("process_family") or _prediction_process_family(prediction),
        }

    item = dict(photo)
    require_production_raw_photo(item)

    original_path = DATA_DIR / item["original_path"]
    if not original_path.exists():
        raise HTTPException(404, "קובץ ה-RAW המקורי לא נמצא")

    process_family = _prediction_process_family(prediction)
    render_id = str(uuid.uuid4())
    source_stem = Path(item["original_name"]).stem
    rendered_rel = (
        f"events/{item['event_id']}/edited/ai/"
        f"{photo_id}_{source_stem}_profile_v{prediction['profile_version_number']}_{render_id[:8]}.jpg"
    )
    rendered_path = DATA_DIR / rendered_rel

    width, height, clean_recipe, process_family = render_production_recipe_preview(
        original_path,
        prediction.get("recipe") or {},
        rendered_path,
        process_family=process_family,
        source_is_raw=True,
    )

    # The canonical recipe stays authoritative. Rendering is only an approximation.
    prediction = dict(prediction)
    prediction["recipe"] = clean_recipe

    with db() as conn:
        saved = save_prediction_preview_render(
            conn,
            photo_id=photo_id,
            prediction=prediction,
            rendered_path=rendered_rel,
            width=width,
            height=height,
            process_family=process_family,
        )

    return {
        "prediction": prediction,
        "render": _production_render_public(request, saved),
        "prediction_reused": prediction_reused,
        "render_reused": False,
        "process_family": process_family,
    }


@app.get("/api/photos/{photo_id}/ai/xmp-test", dependencies=[Depends(require_user)])
def download_ai_prediction_xmp_test(
    photo_id: str,
    user=Depends(require_user),
):
    """
    Download the CURRENT Active-Profile prediction as a Lightroom XMP sidecar
    without approving/correcting the photo and without creating learning data.

    This is deliberately a diagnostic/product-truth route: Adobe Lightroom is
    authoritative for absolute WB / Develop interpretation; the local preview
    remains an approximation.
    """
    prediction, _reused = _infer_photo_with_active_profile(photo_id, user["id"])

    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user["id"]),
        ).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")

        registry = conn.execute(
            """
            SELECT * FROM ai_profile_registries
            WHERE id=? AND user_id=?
            """,
            (prediction["registry_id"], user["id"]),
        ).fetchone()
        if not registry:
            raise HTTPException(409, "AI Profile registry לא נמצא")

    process_family = _prediction_process_family(prediction)
    adobe_meta = dominant_lightroom_source_metadata(
        ai_profiles_dir=AI_PROFILES_DIR,
        user_id=user["id"],
        source_profile_import_id=str(registry["source_profile_import_id"]),
    )
    xmp = build_lightroom_xmp(
        source_name=str(photo["original_name"]),
        recipe=prediction.get("recipe") or {},
        process_family=process_family,
        adobe_metadata=adobe_meta,
    )
    filename = f"{Path(str(photo['original_name'])).stem}.xmp"
    return Response(
        content=xmp,
        media_type="application/rdf+xml; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-ProGrapher-Profile-Version": str(prediction["profile_version_number"]),
        },
    )


@app.post("/api/photos/{photo_id}/ai/darkroom/prepare", dependencies=[Depends(require_user)])
def prepare_production_darkroom(
    photo_id: str,
    request: Request,
    user=Depends(require_user),
):
    prepared = _ensure_prediction_darkroom_render(
        photo_id=photo_id,
        user_id=user["id"],
        request=request,
    )
    return {
        "ok": True,
        "darkroom_mode": "production_profile",
        "recipe_contract": recipe_contract_public(),
        "preview_notice": "RAW-safe local preview. The original RAW is developed once; Lightroom/XMP remains the authoritative final render.",
        **prepared,
    }


@app.post("/api/photos/{photo_id}/ai/darkroom/preview", dependencies=[Depends(require_user)])
def preview_production_darkroom_correction(
    photo_id: str,
    payload: ProductionDarkroomPreviewRequest,
    request: Request,
    user=Depends(require_user),
):
    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user["id"]),
        ).fetchone()
        active_registry = get_default_active_profile(conn, user_id=user["id"])
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        prediction = latest_prediction_for_photo(
            conn,
            photo_id=photo_id,
            profile_version_id=active_version_id,
        )

    if not photo:
        raise HTTPException(404, "התמונה לא נמצאה")
    if not prediction:
        raise HTTPException(409, "אין תחזית Production פעילה לתמונה")

    item = dict(photo)
    require_production_raw_photo(item)

    original_path = DATA_DIR / item["original_path"]
    if not original_path.exists():
        raise HTTPException(404, "קובץ ה-RAW המקורי לא נמצא")

    process_family = _prediction_process_family(prediction)
    clean_recipe = canonicalize_recipe(payload.recipe)

    rendered_rel = (
        f"events/{item['event_id']}/edited/ai/live/"
        f"{photo_id}_production_correction_preview.jpg"
    )
    rendered_path = DATA_DIR / rendered_rel
    width, height, clean_recipe, process_family = render_production_recipe_preview(
        original_path,
        clean_recipe,
        rendered_path,
        process_family=process_family,
        source_is_raw=True,
    )
    created_at = utc_now()

    return {
        "ok": True,
        "photo_id": photo_id,
        "prediction_id": prediction["id"],
        "profile_version_id": prediction["profile_version_id"],
        "recipe_contract_version": prediction["recipe_contract_version"],
        "process_family": process_family,
        "recipe": clean_recipe,
        "rendered_path": rendered_rel,
        "rendered_url": url_for_media(request, rendered_rel),
        "width": width,
        "height": height,
        "preview_is_approximation": True,
        "created_at": created_at,
    }


@app.post("/api/photos/{photo_id}/analyze", dependencies=[Depends(require_user)])
def analyze_photo(photo_id: str):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    item = dict(row)
    if not item.get("preview_path"):
        raise HTTPException(400, "אין preview זמין לניתוח")

    preview_path = DATA_DIR / item["preview_path"]
    if not preview_path.exists():
        raise HTTPException(404, "קובץ ה-preview לא נמצא")

    analysis_payload = analyze_image_from_preview(preview_path)

    base_recipe = sanitize_recipe(analysis_payload["recipe"])
    style_dna = calculate_style_dna(owner_user_id_for_photo(photo_id))
    personalized_recipe = apply_style_dna(base_recipe, style_dna)

    analysis_payload["base_recipe"] = base_recipe
    analysis_payload["recipe"] = personalized_recipe
    analysis_payload["style_dna"] = {
        "version": style_dna["version"],
        "sample_count": style_dna["sample_count"],
        "correction_count": style_dna["correction_count"],
        "approval_count": style_dna["approval_count"],
        "confidence_percent": style_dna["confidence_percent"],
        "learning_strength_percent": style_dna["learning_strength_percent"],
        "bias": style_dna["bias"],
        "top_adjustments": style_dna["top_adjustments"],
        "status_he": style_dna["status_he"],
    }

    if style_dna["sample_count"] > 0:
        analysis_payload["assessment"]["summary_he"] += (
            f" הוחלה מפת הסגנון שנלמדה מ־{style_dna['sample_count']} החלטות קודמות."
        )

    analysis_id = str(uuid.uuid4())
    created_at = utc_now()

    with db() as conn:
        conn.execute(
            """
            INSERT INTO photo_analyses
            (id, photo_id, analysis_json, recipe_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                photo_id,
                json.dumps(analysis_payload, ensure_ascii=False),
                json.dumps(personalized_recipe, ensure_ascii=False),
                created_at,
            ),
        )

    return {
        "ok": True,
        "analysis_id": analysis_id,
        "photo_id": photo_id,
        "created_at": created_at,
        **analysis_payload,
    }

@app.get("/api/photos/{photo_id}/analysis-latest", dependencies=[Depends(require_user)])
def photo_analysis_latest(photo_id: str):
    latest = latest_analysis_for_photo(photo_id)
    if not latest:
        return {"ok": True, "exists": False, "analysis": None}

    row = dict(latest)
    return {
        "ok": True,
        "exists": True,
        "analysis_id": row["id"],
        "photo_id": row["photo_id"],
        "created_at": row["created_at"],
        "analysis": json.loads(row["analysis_json"]),
        "recipe": json.loads(row["recipe_json"]),
    }


@app.post("/api/photos/{photo_id}/render-preview", dependencies=[Depends(require_user)])
def render_preview_from_recipe(photo_id: str, request: Request):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    item = dict(row)
    if not item.get("preview_path"):
        raise HTTPException(400, "אין preview זמין ל-render")

    latest_analysis = latest_analysis_for_photo(photo_id)
    if not latest_analysis:
        raise HTTPException(400, "יש להריץ ניתוח תמונה לפני render")

    analysis_dict = dict(latest_analysis)
    recipe = sanitize_recipe(json.loads(analysis_dict["recipe_json"]))

    preview_path = DATA_DIR / item["preview_path"]
    if not preview_path.exists():
        raise HTTPException(404, "קובץ ה-preview לא נמצא")

    ext = Path(item["original_name"]).stem
    rendered_rel = f"events/{item['event_id']}/edited/{photo_id}_{ext}_rendered.jpg"
    rendered_path = DATA_DIR / rendered_rel

    width, height = render_recipe_on_preview(preview_path, recipe, rendered_path)

    render_id = str(uuid.uuid4())
    created_at = utc_now()

    with db() as conn:
        conn.execute(
            """
            INSERT INTO photo_renders
            (id, photo_id, recipe_json, rendered_path, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                render_id,
                photo_id,
                json.dumps(recipe, ensure_ascii=False),
                rendered_rel,
                width,
                height,
                created_at,
            ),
        )

        conn.execute(
            """
            UPDATE photos
            SET edited_path = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                rendered_rel,
                "rendered",
                created_at,
                photo_id,
            ),
        )

        updated = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    output = row_to_photo(request, updated, include_metadata=True)
    output["latest_render"] = {
        "id": render_id,
        "photo_id": photo_id,
        "recipe_json": json.dumps(recipe, ensure_ascii=False),
        "rendered_path": rendered_rel,
        "width": width,
        "height": height,
        "created_at": created_at,
    }

    return {
        "ok": True,
        "photo": output,
        "recipe": recipe,
        "render_id": render_id,
        "created_at": created_at,
    }


@app.post("/api/photos/{photo_id}/render-custom-preview", dependencies=[Depends(require_user)])
def render_custom_preview(
    photo_id: str,
    payload: CustomRenderRequest,
    request: Request,
):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    item = dict(row)
    if not item.get("preview_path"):
        raise HTTPException(400, "אין preview זמין לעריכה")

    preview_path = DATA_DIR / item["preview_path"]
    if not preview_path.exists():
        raise HTTPException(404, "קובץ ה-preview לא נמצא")

    recipe = sanitize_recipe(payload.recipe)
    source_stem = Path(item["original_name"]).stem

    if payload.commit:
        render_id = str(uuid.uuid4())
        rendered_rel = (
            f"events/{item['event_id']}/edited/"
            f"{photo_id}_{source_stem}_corrected_{render_id[:8]}.jpg"
        )
    else:
        render_id = None
        rendered_rel = (
            f"events/{item['event_id']}/edited/"
            f"{photo_id}_{source_stem}_correction_preview.jpg"
        )

    rendered_path = DATA_DIR / rendered_rel
    width, height = render_recipe_on_preview(preview_path, recipe, rendered_path)
    created_at = utc_now()

    if payload.commit:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO photo_renders
                (id, photo_id, recipe_json, rendered_path, width, height, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    render_id,
                    photo_id,
                    json.dumps(recipe, ensure_ascii=False),
                    rendered_rel,
                    width,
                    height,
                    created_at,
                ),
            )
            conn.execute(
                """
                UPDATE photos
                SET edited_path = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    rendered_rel,
                    "corrected",
                    created_at,
                    photo_id,
                ),
            )

    return {
        "ok": True,
        "committed": payload.commit,
        "render_id": render_id,
        "photo_id": photo_id,
        "recipe": recipe,
        "rendered_path": rendered_rel,
        "rendered_url": url_for_media(request, rendered_rel),
        "width": width,
        "height": height,
        "created_at": created_at,
    }

@app.get("/api/photos/{photo_id}/render-latest", dependencies=[Depends(require_user)])
def photo_render_latest(photo_id: str, request: Request):
    latest = latest_render_for_photo(photo_id)
    if not latest:
        return {"ok": True, "exists": False, "render": None}

    row = dict(latest)

    with db() as conn:
        photo_row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    output = row_to_photo(request, photo_row, include_metadata=True) if photo_row else None

    return {
        "ok": True,
        "exists": True,
        "render": row,
        "photo": output,
    }

@app.post("/api/photos/{photo_id}/refresh-metadata", dependencies=[Depends(require_user)])
def refresh_photo_metadata(photo_id: str, request: Request):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "התמונה לא נמצאה")

    item = dict(row)
    source = DATA_DIR / item["original_path"]
    metadata = extract_photo_metadata(
        source,
        width=item.get("width"),
        height=item.get("height"),
    )
    save_metadata_sidecar(item["event_id"], item["id"], metadata)

    with db() as conn:
        conn.execute(
            """
            UPDATE photos
            SET metadata_json = ?, metadata_updated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(metadata, ensure_ascii=False),
                utc_now(),
                utc_now(),
                photo_id,
            ),
        )
        updated = conn.execute(
            "SELECT * FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

    return row_to_photo(request, updated, include_metadata=True)



def _learning_public_with_render(request: Request, sample: Optional[dict]) -> Optional[dict]:
    if not sample:
        return None
    item = dict(sample)
    render_path = item.get("final_render_path")
    if render_path and (DATA_DIR / render_path).exists():
        item["final_render_url"] = url_for_media(request, render_path)
    else:
        item["final_render_url"] = None
    return item


@app.get("/api/photos/{photo_id}/ai/decision-latest", dependencies=[Depends(require_user)])
def get_latest_production_learning_decision(
    photo_id: str,
    request: Request,
    user=Depends(require_user),
):
    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.id
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user["id"]),
        ).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")

        active_registry = get_default_active_profile(conn, user_id=user["id"])
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        sample = latest_learning_for_photo(
            conn,
            photo_id=photo_id,
            profile_version_id=active_version_id,
        )

    return {
        "ok": True,
        "exists": sample is not None,
        "learning_format": LEARNING_SAMPLE_FORMAT,
        "decision": _learning_public_with_render(request, sample),
    }


@app.post("/api/photos/{photo_id}/ai/decision", dependencies=[Depends(require_user)])
def save_production_learning_decision(
    photo_id: str,
    payload: ProductionLearningDecisionRequest,
    request: Request,
    user=Depends(require_user),
):
    verdict = str(payload.verdict or "").strip().lower()
    if verdict not in {"approved", "corrected"}:
        raise HTTPException(400, "החלטת למידה חייבת להיות approved או corrected")

    # Always resolve the current ACTIVE-profile prediction server-side.
    # The client is never trusted to tell us which AI recipe/profile produced it.
    prediction, _prediction_reused = _infer_photo_with_active_profile(
        photo_id,
        user["id"],
    )

    with db() as conn:
        photo = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN events e ON e.id=p.event_id
            WHERE p.id=? AND e.user_id=?
            """,
            (photo_id, user["id"]),
        ).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")

        brain = conn.execute(
            """
            SELECT *
            FROM photo_brain_vision
            WHERE id=? AND photo_id=?
            """,
            (prediction["brain_analysis_id"], photo_id),
        ).fetchone()
        if not brain:
            raise HTTPException(409, "רשומת Vision של התחזית אינה זמינה")

        process_family = _prediction_process_family(prediction)

        try:
            sample = save_learning_decision(
                conn,
                user_id=user["id"],
                photo_row=photo,
                brain_row=brain,
                prediction=prediction,
                verdict=verdict,
                photographer_recipe=payload.photographer_recipe,
                process_family=process_family,
                note=payload.note or "",
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc

    # Persist a visual FINAL preview for the photographer.  This is still only a
    # preview approximation; the canonical final recipe in the learning sample
    # remains the source of truth.
    final_render_rel = None
    item = dict(photo)
    if item.get("preview_path"):
        preview_path = DATA_DIR / item["preview_path"]
        if preview_path.exists():
            final_render_rel = (
                f"events/{item['event_id']}/edited/final/"
                f"{photo_id}_decision_{sample['id'][:8]}.jpg"
            )
            final_render_path = DATA_DIR / final_render_rel
            try:
                render_production_recipe_preview(
                    preview_path,
                    sample["photographer_recipe"],
                    final_render_path,
                    process_family=process_family,
                )
            except Exception:
                final_render_rel = None

    with db() as conn:
        if final_render_rel:
            sample = set_learning_final_render(
                conn,
                sample_id=sample["id"],
                final_render_path=final_render_rel,
            )

        conn.execute(
            """
            UPDATE photos
            SET status=?, updated_at=?
            WHERE id=?
            """,
            (
                "אושר" if verdict == "approved" else "תוקן",
                utc_now(),
                photo_id,
            ),
        )

        summary = learning_summary(conn, user_id=user["id"])

    return {
        "ok": True,
        "learning_format": LEARNING_SAMPLE_FORMAT,
        "decision": _learning_public_with_render(request, sample),
        "learning_summary": summary,
    }


@app.get("/api/ai/learning/summary", dependencies=[Depends(require_user)])
def get_production_learning_summary(user=Depends(require_user)):
    with db() as conn:
        active_registry = get_default_active_profile(conn, user_id=user["id"])
        active_version_id = (
            active_registry["active_version"]["id"]
            if active_registry and active_registry.get("active_version")
            else None
        )
        all_versions = learning_summary(conn, user_id=user["id"])
        active_version = learning_summary(
            conn,
            user_id=user["id"],
            profile_version_id=active_version_id,
        ) if active_version_id else None

    return {
        "ok": True,
        "learning_format": LEARNING_SAMPLE_FORMAT,
        "all_versions": all_versions,
        "active_profile_version": active_version,
    }


@app.get("/api/photos/{photo_id}/feedback-latest", dependencies=[Depends(require_user)])
def get_latest_feedback(photo_id: str):
    row = latest_feedback_for_photo(photo_id)
    if not row:
        return {"ok": True, "exists": False, "feedback": None}
    output = dict(row)
    return {"ok": True, "exists": True, "feedback": output}

@app.post("/api/photos/{photo_id}/feedback", dependencies=[Depends(require_user)])
def add_feedback(photo_id: str, payload: FeedbackCreate):
    with db() as conn:
        photo = conn.execute("SELECT id FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if not photo:
            raise HTTPException(404, "התמונה לא נמצאה")

        feedback_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO feedback
            (id, photo_id, verdict, ai_recipe_json, photographer_recipe_json, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                photo_id,
                payload.verdict,
                json.dumps(payload.ai_recipe, ensure_ascii=False) if payload.ai_recipe else None,
                json.dumps(payload.photographer_recipe, ensure_ascii=False)
                if payload.photographer_recipe
                else None,
                payload.note,
                utc_now(),
            ),
        )
    return {"ok": True, "id": feedback_id}


@app.get("/api/style/dna", dependencies=[Depends(require_user)])
def get_style_dna(user=Depends(require_user)):
    return calculate_style_dna(user["id"])

@app.post("/api/style/dna/rebuild", dependencies=[Depends(require_user)])
def rebuild_style_dna(user=Depends(require_user)):
    return {"ok": True,"dna":calculate_style_dna(user["id"]),"rebuilt_at":utc_now()}

@app.get("/api/style/profile", dependencies=[Depends(require_user)])
def get_style_profile(user=Depends(require_user)):
    with db() as conn:
        onboarding=_user_onboarding(conn,user["id"])
        pairs=conn.execute("SELECT COUNT(*) c FROM style_pairs WHERE user_id=?",(user["id"],)).fetchone()["c"]
    return {"id":user["id"],"description":onboarding.get("notes",""),"calibration_score":calculate_style_dna(user["id"])["confidence_percent"],"updated_at":utc_now(),"pair_count":pairs}

@app.put("/api/style/profile", dependencies=[Depends(require_user)])
def update_style_profile(payload: StyleProfileUpdate, user=Depends(require_user)):
    with db() as conn:
        current=_user_onboarding(conn,user["id"])
        conn.execute("""INSERT INTO user_onboarding (user_id,specialties_json,editor_software,style_words_json,priorities_json,notes,completed,updated_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET notes=excluded.notes,updated_at=excluded.updated_at""",(user["id"],json.dumps(current["specialties"],ensure_ascii=False),current["editor_software"],json.dumps(current["style_words"],ensure_ascii=False),json.dumps(current["priorities"],ensure_ascii=False),payload.description,1 if current["completed"] else 0,utc_now()))
    return {"id":user["id"],"description":payload.description,"calibration_score":payload.calibration_score,"updated_at":utc_now()}

@app.post("/api/style/pairs", dependencies=[Depends(require_user)])
async def upload_style_pair(original: UploadFile=File(...),edited: UploadFile=File(...),scene_label: str=Form(default=""),user=Depends(require_user)):
    pair_id=str(uuid.uuid4()); pair_dir=STYLE_DIR/user["id"]/"pairs"/pair_id; pair_dir.mkdir(parents=True,exist_ok=True)
    original_name=clean_filename(original.filename or "original"); edited_name=clean_filename(edited.filename or "edited")
    original_path=pair_dir/f"original_{original_name}"; edited_path=pair_dir/f"edited_{edited_name}"
    with original_path.open("wb") as out:
        while chunk := await original.read(1024*1024): out.write(chunk)
    with edited_path.open("wb") as out:
        while chunk := await edited.read(1024*1024): out.write(chunk)
    with db() as conn:
        conn.execute("""INSERT INTO style_pairs (id,original_name,edited_name,original_path,edited_path,scene_label,created_at,user_id) VALUES (?,?,?,?,?,?,?,?)""",(pair_id,original_name,edited_name,original_path.relative_to(DATA_DIR).as_posix(),edited_path.relative_to(DATA_DIR).as_posix(),scene_label,utc_now(),user["id"]))
    return {"ok":True,"id":pair_id}

@app.get("/api/style/pairs", dependencies=[Depends(require_user)])
def list_style_pairs(user=Depends(require_user)):
    with db() as conn: rows=conn.execute("SELECT id,original_name,edited_name,scene_label,created_at FROM style_pairs WHERE user_id=? ORDER BY created_at DESC",(user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/media/{relative_path:path}")
def media(relative_path: str):
    # Prevent path traversal.
    target = (DATA_DIR / relative_path).resolve()
    if DATA_DIR.resolve() not in target.parents and target != DATA_DIR.resolve():
        raise HTTPException(400, "נתיב לא תקין")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "הקובץ לא נמצא")
    return FileResponse(target)

@app.get("/api/debug/routes")
def routes():
    return sorted(
        [
            {
                "path": route.path,
                "methods": sorted(list(route.methods or [])),
                "name": route.name,
            }
            for route in app.routes
            if hasattr(route, "methods")
        ],
        key=lambda x: x["path"],
    )
