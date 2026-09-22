# Phase 11 Part 5B — ExifTool camera metadata integration

## Scope

This change closes the current Windows CR3 camera-identity gap without guessing
from the filename.

Priority is conservative:

1. Existing source/manifest metadata wins.
2. ExifTool fills only missing camera make/model, capture time and lens model.
3. rawpy/LibRaw continues to fill numeric exposure metadata and RAW WB.
4. If ExifTool is unavailable or fails, missing values stay missing.
5. The feature contract is bumped to `brain-v2-features-v1.3` because
   `camera.make` / `camera.model` categorical context can now change for the
   same RAW input.

ExifTool is intentionally **not redistributed by this patch**. The local
development copy remains under `backend/vendor/exiftool/` and is git-ignored
until desktop packaging/licensing is handled deliberately.

## Real verification

Use:

```cmd
cd "C:\Users\Matann\Desktop\PROGRAPHER V2\backend"

.\.venv\Scripts\python.exe tools\phase11_exiftool_brain_probe.py ^
  --raw "C:\Users\Matann\Desktop\raw_test\Canon_EOS_R6_RAW_ISO_100_nocrop_nodual.CR3" ^
  --expect-make "Canon" ^
  --expect-model "Canon EOS R6" ^
  --output "..\docs\runtime\phase11_exiftool_brain_probe.json"
```

Then run the full tests. Do not commit until both pass.
