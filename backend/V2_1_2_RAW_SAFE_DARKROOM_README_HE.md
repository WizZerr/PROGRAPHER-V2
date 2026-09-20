# ProGrapher Backend V2.1.2 — RAW Safe Darkroom

Smoke Test hotfix after discovering destructive-looking previews on JPG.

## What changed

### 1. Production event editing is RAW-only
Accepted:
- CR2 / CR3
- NEF
- ARW
- DNG
- ORF
- RW2
- RAF
- PEF

JPG / PNG / WEBP / TIFF are rejected before an event upload writes any files.

### 2. No more double-development
Old path:
RAW/JPG -> already-developed JPEG preview -> apply Exposure/WB again

New path:
Original RAW -> rawpy development ONCE -> local preview controls

Exposure is applied during RAW development and is NOT multiplied again after JPEG conversion.

### 3. Conservative local preview
Contrast, color, Legacy controls and clarity are intentionally milder in the local preview.
The canonical Recipe is unchanged.

### 4. Lightroom remains authoritative
The browser preview is still not Adobe Camera Raw.
Final truth remains the canonical Recipe exported to Lightroom-compatible XMP.

No database reset and no profile retraining are required.
