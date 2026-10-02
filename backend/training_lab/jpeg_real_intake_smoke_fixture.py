from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2

from jpeg_j0_feasibility import _apply_recipe_uint8, _write_jpeg
from jpeg_j0_synthetic_benchmark import _make_scene, _recipe, SUPPORTED_CASES


EVENT_COUNT = 5
PAIRS_PER_EVENT = 4


def _crop_center(image, fraction: float = 0.88):
    height, width = image.shape[:2]
    crop_w = max(1, round(width * fraction))
    crop_h = max(1, round(height * (fraction - 0.08)))
    x = max(0, (width - crop_w) // 2)
    y = max(0, (height - crop_h) // 2)
    return image[y : y + crop_h, x : x + crop_w]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic multi-event Original/Edited JPEG fixture for "
            "testing the real-dataset intake pipeline without photographer material."
        )
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if args.clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    usable_expected = 0
    unchanged_expected = 0
    geometry_expected = 0

    for event_index in range(1, EVENT_COUNT + 1):
        event = output / f"event_{event_index:02d}"
        originals = event / "ORIGINALS"
        edits = event / "EDITS"
        originals.mkdir(parents=True, exist_ok=True)
        edits.mkdir(parents=True, exist_ok=True)

        for image_index in range(1, PAIRS_PER_EVENT + 1):
            global_index = (event_index - 1) * PAIRS_PER_EVENT + image_index
            original = _make_scene(global_index, width=960, height=640)
            case_name = SUPPORTED_CASES[(global_index - 1) % len(SUPPORTED_CASES)]
            edited = _apply_recipe_uint8(original, _recipe(case_name))

            name = f"IMG_{event_index:02d}_{image_index:03d}.jpg"
            original_path = originals / name
            edited_path = edits / name
            _write_jpeg(original_path, original, quality=98)

            if event_index == 2 and image_index == 1:
                # Real exports can contain a final that is byte-identical to the
                # source. Preserve this as an explicit identity/unedited case.
                shutil.copyfile(original_path, edited_path)
                unchanged_expected += 1
            elif event_index == 3 and image_index == 1:
                cropped = _crop_center(edited)
                _write_jpeg(edited_path, cropped, quality=98)
                geometry_expected += 1
            else:
                _write_jpeg(edited_path, edited, quality=98)
                usable_expected += 1

        # Confirm non-JPEG noise is ignored rather than treated as a photo pair.
        (originals / "notes.txt").write_text(
            "synthetic intake smoke fixture",
            encoding="utf-8",
        )

    print("=" * 80)
    print("ProGrapher — JPEG real-intake smoke fixture")
    print("=" * 80)
    print(f"Events:                           {EVENT_COUNT}")
    print(f"Pairs per event:                  {PAIRS_PER_EVENT}")
    print(f"Expected usable recipe pairs:     {usable_expected}")
    print(f"Expected unchanged-final pairs:   {unchanged_expected}")
    print(f"Expected geometry exclusions:     {geometry_expected}")
    print(f"Fixture root:                     {output}")
    print()
    print("This is synthetic engineering material, not photographer training data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
