from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


XMP_EXTENSION = ".xmp"


@dataclass(frozen=True)
class EditsFolderProbe:
    path: str
    exists: bool
    readable: bool
    xmp_files: int
    note: str


def probe_edits_folder(path: str | Path) -> EditsFolderProbe:
    folder = Path(path).expanduser()

    if not folder.exists():
        return EditsFolderProbe(
            path=str(folder),
            exists=False,
            readable=False,
            xmp_files=0,
            note="תיקיית העריכות שנבחרה אינה קיימת.",
        )

    if not folder.is_dir():
        return EditsFolderProbe(
            path=str(folder),
            exists=True,
            readable=False,
            xmp_files=0,
            note="הנתיב שנבחר אינו תיקייה.",
        )

    try:
        root = folder.resolve(strict=True)
        xmp_files = sum(
            1
            for item in root.rglob("*")
            if item.is_file() and item.suffix.lower() == XMP_EXTENSION
        )
    except OSError as exc:
        return EditsFolderProbe(
            path=str(folder),
            exists=True,
            readable=False,
            xmp_files=0,
            note=f"לא ניתן לקרוא את תיקיית העריכות: {exc}",
        )

    if xmp_files == 0:
        note = (
            "לא נמצאו קובצי XMP בתיקייה. אפשר לשמור את המקור, "
            "אך עדיין אין ממנו יעדי עריכה ללמידה."
        )
    else:
        note = (
            f"נמצאו {xmp_files} קובצי XMP. "
            "התאמת XMP ל-RAW תתבצע בשלב Dataset ולא נספרת עדיין כדוגמאות תקינות."
        )

    return EditsFolderProbe(
        path=str(root),
        exists=True,
        readable=True,
        xmp_files=xmp_files,
        note=note,
    )
