from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this file directly from backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.lightroom_reference_exercise import (  # noqa: E402
    ObservedLightroomRecipe,
    create_exercise,
    verify_exercise,
)


def _float_prompt(label: str) -> float:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return float(raw)
        except ValueError:
            print("ערך לא חוקי. נסה שוב.")


def _int_prompt(label: str) -> int:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return int(raw)
        except ValueError:
            print("ערך לא חוקי. נסה שוב.")


def _text_prompt(label: str) -> str:
    while True:
        raw = input(f"{label}: ").strip()
        if raw:
            return raw
        print("הערך לא יכול להיות ריק.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ProGrapher Lightroom 15A/22A/23A reference exercise"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    source = prepare.add_mutually_exclusive_group(required=True)
    source.add_argument("--raw")
    source.add_argument("--raw-folder")
    prepare.add_argument("--workspace-root")

    verify = sub.add_parser("verify")
    verify.add_argument("--workspace", required=True)
    verify.add_argument("--render")

    args = parser.parse_args()

    if args.command == "prepare":
        workspace = create_exercise(
            raw_path=args.raw,
            raw_folder=args.raw_folder,
            workspace_root=args.workspace_root,
        )

        steps = workspace / "LIGHTROOM_STEPS.txt"
        print()
        print("✅ בדיקת Lightroom הוכנה")
        print(f"Workspace: {workspace}")
        print(f"הוראות: {steps}")
        print()
        print(steps.read_text(encoding="utf-8"))
        return 0

    print()
    print("הקלד בדיוק את הערכים שמופיעים כרגע ב-Lightroom:")
    observed = ObservedLightroomRecipe(
        exposure=_float_prompt("Exposure"),
        temperature=_int_prompt("Temperature"),
        tint=_int_prompt("Tint"),
        blacks=_float_prompt("Blacks"),
        process_version=_text_prompt("Process Version"),
        camera_profile=_text_prompt("Camera Profile"),
    )

    result = verify_exercise(
        workspace=args.workspace,
        observed=observed,
        render_path=args.render,
    )

    print()
    if result.status == "PASS":
        print("✅ PASS — Lightroom Reference Round-trip תקין")
    else:
        print("❌ FAIL — הבדיקה אינה תואמת")

    print(f"RAW מקור ללא שינוי: {result.source_unchanged}")
    print(f"RAW בדיקה ללא שינוי: {result.fixture_raw_unchanged}")
    print(f"מתכון תואם: {result.recipe_matches}")
    print(f"רינדור קיים: {result.render_exists}")
    print(f"XMP קיים: {result.xmp_present}")
    print(f"ACR קיים: {result.acr_present}")

    if result.mismatches:
        print("שדות שלא תאמו: " + ", ".join(result.mismatches))

    print(
        "Result: "
        + str(Path(args.workspace).expanduser().resolve() / "result.json")
    )

    return 0 if result.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
