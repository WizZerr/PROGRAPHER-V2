"""RAW-CAT-01F.03A — private, bounded source-RAW / catalog per-photo pilot.

This creates research candidates, NOT approved training pairs. Input features come
ONLY from original RAW; Lightroom Develop metadata lives under 'target' and is
never an input. All per-photo records remain in the explicitly private output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from app.brain_v2.preprocessing.raw_decode import RAW_PREPROCESSING_VERSION, decode_raw
from app.photographer.raw_catalog_intake import (
    CatalogIntakeError, _write_atomic, inspect_catalog,
)
from app.photographer.raw_visual_context_probe import describe_linear_rgb

SCHEMA = "prographer.raw_catalog_context_pilot.v0"
ALLOWED_INPUT_METADATA = (
    "iso_speed", "shutter_seconds", "aperture", "focal_length_mm",
)


def _key(stem: str, ext: str) -> tuple[str, str]:
    return stem.casefold(), ext.lstrip(".").casefold()


def _index_originals(root: Path) -> dict[tuple[str, str], list[Path]]:
    index: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for candidate in root.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if candidate.name.startswith("._") or candidate.suffix.casefold() != ".cr3":
            continue
        index[_key(candidate.stem, candidate.suffix)].append(candidate)
    return index


def _candidate_selection(
    files: dict[tuple[str, str], list[Path]],
    records: list[dict],
    max_files: int,
) -> tuple[list[tuple[Path, dict]], Counter[str]]:
    if not 1 <= max_files <= 20:
        raise ValueError("--max-files must be 1..20")
    by_name: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        stem, ext = record.get("file_stem"), record.get("extension")
        if isinstance(stem, str) and stem.strip() and isinstance(ext, str):
            by_name[_key(stem, ext)].append(record)
    groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    for key, source_files in files.items():
        matching = by_name.get(key, [])
        if not matching:
            statuses["no_catalog_match"] += len(source_files)
            continue
        if len(source_files) != 1 or len(matching) != 1:
            statuses["ambiguous_name_key"] += 1
            continue
        row = matching[0]
        if row.get("parse_exclusion"):
            statuses["catalog_parse_excluded"] += 1
        elif row.get("virtual_copy_candidate"):
            statuses["virtual_copy_review"] += 1
        else:
            groups[str(row.get("event_group_id") or "UNKNOWN")].append((source_files[0], row))
    for group in groups.values():
        group.sort(key=lambda pair: pair[0].name.casefold())

    # Round-robin across PROVISIONAL catalog groups; NOT confirmed events or
    # verified independent lighting conditions.
    group_keys = sorted(groups)
    selected: list[tuple[Path, dict]] = []
    cursor = 0
    while len(selected) < max_files and group_keys:
        key = group_keys[cursor % len(group_keys)]
        if groups[key]:
            selected.append(groups[key].pop(0))
        if not groups[key]:
            group_keys.remove(key)
            cursor = 0
        else:
            cursor += 1
    statuses["candidate_selected"] = len(selected)
    return selected, statuses


def build_pilot(
    raw_dir: str | Path, catalog: str | Path, max_files: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(raw_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--raw-dir must be a directory")
    _, catalog_private = inspect_catalog(catalog, include_private=True)
    if catalog_private is None:
        raise ValueError("catalog has no private records")
    files = _index_originals(root)
    selected, selection_counts = _candidate_selection(
        files, catalog_private["records"], max_files
    )
    if not selected:
        raise ValueError("no unique RAW/catalog filename candidates")

    output_rows: list[dict[str, Any]] = []
    failures: Counter[str] = Counter()
    for path, catalog_row in selected:
        try:
            frame = decode_raw(path)
            features = describe_linear_rgb(frame.rgb_linear)
            meta = frame.metadata
            # Intentional narrow allowlist: camera/RAW metadata, NEVER catalog
            # exposure/Develop, edited previews, sidecars, final JPEG or masks.
            camera = {
                k: getattr(meta, k, None) for k in ALLOWED_INPUT_METADATA
            }
            output_rows.append({
                "provenance_PRIVATE": {
                    "raw_name": path.name,
                    "raw_path": str(path),
                    "raw_sha256": frame.source_sha256,
                    "catalog_image_id": catalog_row.get("catalog_image_id"),
                    "provisional_catalog_group": catalog_row.get("event_group_id"),
                    "name_and_extension_match_only": True,
                    "content_identity_to_catalog_verified": False,
                },
                "model_input_RESEARCH_ONLY": {
                    "source": "original_RAW_only",
                    "pipeline_version": meta.preprocessing_version,
                    "raw_engine": meta.raw_engine,
                    "raw_engine_version": meta.raw_engine_version,
                    "camera_metadata": camera,
                    "source_visual_features": features,
                },
                "target_UNAPPROVED_RESEARCH_ONLY": {
                    "lightroom_develop": catalog_row.get("develop", {}),
                    "curve_and_opaque_evidence": catalog_row.get("complex", {}),
                    "unsupported_fields": catalog_row.get("unsupported_fields", []),
                    "has_opaque_local_edits": bool(
                        catalog_row.get("opaque_edit_review_required")
                    ),
                },
                "photographer_review_PRIVATE": {
                    "scene_label": "UNKNOWN",
                    "event_id": None,
                    "photographer_final_edit_confirmed": False,
                    "photographer_event_confirmed": False,
                    "independent_raw_identity_confirmed": False,
                    "approved_for_training": False,
                },
            })
            del frame
        except (OSError, ValueError, RuntimeError, MemoryError) as exc:
            # Some rawpy exceptions contain source filenames; aggregate only.
            failures[type(exc).__name__] += 1
    keys = tuple(output_rows[0]["model_input_RESEARCH_ONLY"]["source_visual_features"]) if output_rows else ()
    metrics = {
        key: {
            "min": min(row["model_input_RESEARCH_ONLY"]["source_visual_features"][key] for row in output_rows),
            "median": median(row["model_input_RESEARCH_ONLY"]["source_visual_features"][key] for row in output_rows),
            "max": max(row["model_input_RESEARCH_ONLY"]["source_visual_features"][key] for row in output_rows),
        }
        for key in keys
    }
    group_count: Counter[str] = Counter(
        str(row["provenance_PRIVATE"]["provisional_catalog_group"])
        for row in output_rows
    )
    report = {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_RESEARCH_CANDIDATES_ONLY",
        "privacy": "AGGREGATE only — no filenames, directories, dates, photo IDs, RAW hashes or Lightroom adjustments",
        "raw_pipeline": RAW_PREPROCESSING_VERSION,
        "matching": "unique_case_insensitive_RAW_filename_and_extension_only",
        "selection": "round_robin_provisional_catalog_groups_NOT_human_scene_or_event_strata",
        "raw_files_indexed": sum(map(len, files.values())),
        "selected": len(selected),
        "decoded_and_catalog_linked_candidate": len(output_rows),
        "decode_failures": dict(sorted(failures.items())),
        "selection_counts": dict(sorted(selection_counts.items())),
        "provisional_group_counts": dict(sorted(group_count.items())),
        "visual_feature_aggregates": metrics,
        "confirmed_events": 0,
        "content_verified_catalog_pairs": 0,
        "photographer_confirmed_final_edits": 0,
        "training_ready_pairs": 0,
        "warning": "Read-only, no data leakage, but NOT production training; filename-match is not identity; no permission/finality/event confirmation proof",
    }
    private = {
        "schema": SCHEMA,
        "privacy": "PRIVATE LOCAL ONLY; DO NOT UPLOAD TO PUBLIC REPO OR CHAT",
        "status": "CANDIDATE_RESEARCH_MANIFEST_NOT_TRAINING_DATA",
        "records": output_rows,
        "all_model_inputs_are_RAW_only": True,
        "training_ready_pairs": 0,
    }
    return report, private


def main() -> int:
    cli = argparse.ArgumentParser(description="Bounded RAW-only source features + Lightroom targets (PRIVATE)")
    cli.add_argument("--raw-dir", type=Path, required=True)
    cli.add_argument("--catalog", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True, help="Shareable aggregate JSON")
    cli.add_argument("--private-manifest", type=Path, required=True, help="PRIVATE; DO NOT UPLOAD")
    cli.add_argument("--max-files", type=int, default=12)
    cli.add_argument("--consent-acknowledged", action="store_true",
                     help="Confirm the photographer has allowed LOCAL source RAW research")
    args = cli.parse_args()
    if not args.consent_acknowledged:
        cli.error("Photographer's explicit local research permission is required")
    try:
        root = args.raw_dir.expanduser().resolve(strict=True)
        cat = args.catalog.expanduser().resolve(strict=True)
        report = args.report.expanduser().resolve()
        private_path = args.private_manifest.expanduser().resolve()
        if (report == private_path or report == cat or private_path == cat
                or report.is_relative_to(root) or private_path.is_relative_to(root)):
            raise ValueError("Outputs must be distinct, outside RAW directory and not overwrite catalog")
        shared, private = build_pilot(root, cat, args.max_files)
        # Write private record first so aggregate never falsely signals completion.
        _write_atomic(private_path, private)
        _write_atomic(report, shared)
    except (CatalogIntakeError, OSError, ValueError, MemoryError) as exc:
        cli.exit(2, "SOURCE/TARGET PILOT FAILED (sources unchanged): " + str(exc) + "\n")
    print("Aggregate report:", report)
    print("Private manifest (KEEP LOCAL):", private_path)
    print("Candidate selected:", shared["selected"])
    print("RAW decoded with name-matched catalog rows:", shared["decoded_and_catalog_linked_candidate"])
    print("Decode failures:", sum(shared["decode_failures"].values()))
    print("Training-ready pairs: 0 (identity, finality, event and gates not confirmed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
