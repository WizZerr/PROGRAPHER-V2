from __future__ import annotations

import hashlib
import json
from pathlib import Path

MODELS = (
    {
        "id": "yunet-2026may",
        "role": "face_candidate",
        "path": "vendor/opencv_zoo/face_detection_yunet/face_detection_yunet_2026may.onnx",
        "license": "MIT",
        "license_scope": "OpenCV Zoo face_detection_yunet directory",
        "redistribution_review": "permissive-license-obligations",
        "candidate_status": "basic_negative_positive_validation_passed",
    },
    {
        "id": "pphumanseg-2023mar",
        "role": "subject_candidate_rejected",
        "path": "vendor/opencv_zoo/human_segmentation_pphumanseg/human_segmentation_pphumanseg_2023mar.onnx",
        "license": "Apache-2.0",
        "license_scope": "OpenCV Zoo human_segmentation_pphumanseg directory",
        "redistribution_review": "permissive-license-obligations",
        "candidate_status": "rejected_false_positive_on_sculpture_control",
    },
    {
        "id": "PekingU/rtdetr_r50vd",
        "role": "person_candidate",
        "path": "vendor/huggingface/PekingU_rtdetr_r50vd/model.safetensors",
        "license": "Apache-2.0",
        "license_scope": "Hugging Face model repository metadata + official RT-DETR repository",
        "redistribution_review": "permissive-license-obligations",
        "candidate_status": "basic_negative_positive_validation_passed",
    },
    {
        "id": "openai/clip-vit-base-patch32",
        "role": "vision_encoder_candidate",
        "path": None,
        "license": "MIT for OpenAI CLIP repository software",
        "license_scope": "repository software; pretrained-weight scope not assumed",
        "redistribution_review": "weights-clarification-required-before-bundling",
        "candidate_status": "quality_comparison_blocked_by_representative_dataset",
    },
    {
        "id": "facebook/dinov3-vits16-pretrain-lvd1689m",
        "role": "vision_encoder_candidate",
        "path": None,
        "license": "DINOv3 License",
        "license_scope": "code and model weights under custom DINOv3 agreement",
        "redistribution_review": "custom-license-review-required-before-bundling",
        "candidate_status": "quality_comparison_blocked_by_representative_dataset",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    backend = Path.cwd().resolve()
    if not (backend / "app" / "brain_v2").is_dir():
        raise SystemExit(
            f"Run from the ProGrapher V2 backend directory. Current: {backend}"
        )

    entries = []
    for item in MODELS:
        entry = dict(item)
        relative = item["path"]
        if relative is None:
            entry["local_vendor_file_present"] = None
            entry["size_bytes"] = None
            entry["sha256"] = None
        else:
            path = backend / relative
            entry["local_vendor_file_present"] = path.is_file()
            entry["size_bytes"] = path.stat().st_size if path.is_file() else None
            entry["sha256"] = _sha256(path) if path.is_file() else None
        entries.append(entry)

    report = {
        "schema_version": "phase11-model-license-inventory-v1",
        "legal_note": (
            "Engineering inventory only; license compliance and commercial "
            "redistribution decisions require review of the governing license terms."
        ),
        "models": entries,
    }

    output = backend.parent / "docs" / "runtime" / "phase11_model_license_inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Phase 11 model/license inventory ===")
    for entry in entries:
        print(
            f"{entry['id']}: license={entry['license']} | "
            f"status={entry['candidate_status']} | "
            f"local={entry['local_vendor_file_present']}"
        )
    print(f"Report: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
