# ProGrapher V2 — Regression Checklist

This checklist is intentionally narrower than the Master Plan. It records product behaviors that must not regress while PR #1 is reviewed and while later Brain work is added.

## Startup / shell
- [ ] Tauri app starts without a second manual backend console.
- [ ] Engine reaches Ready without abnormal delay.
- [ ] Dashboard, Events, Gallery, Darkroom, Profile and Training open without runtime errors.
- [ ] Closing and reopening preserves expected local state.

## Source safety
- [x] RAW source hash remains unchanged after XMP export in the validated PR1 flow.
- [x] Photographer/external XMP is not overwritten.
- [x] ProGrapher-owned XMP can be updated safely.
- [x] Same-named files from separate events export into separate event paths.
- [x] Event deletion is catalog-only and leaves source photo files untouched.
- [ ] Final merge smoke repeats source-safety checks on the current merge candidate.

## RAW review
- [x] Supported RAW preview path was manually validated.
- [x] Darkroom next/previous navigation was manually validated.
- [x] Undo/Redo was manually validated.
- [x] Unsaved correction draft survives image navigation.
- [x] Saved correction survives full restart.
- [ ] Final merge smoke confirms the current head still preserves these behaviors.

## JPEG dataset path
- [x] Original/Edited JPEG dataset creation was manually exercised.
- [x] Production UI does not claim a trained JPEG model.
- [x] Production JPEG path does not expose XMP export.
- [ ] Final merge smoke confirms RAW and JPEG profiles remain independent across switching.
- [ ] Final merge smoke confirms gallery JPEG count/preview behavior on the current head.

## Event / storage
- [ ] External-drive disconnect is handled as missing rather than crashing.
- [ ] Relink restores the event after reconnect.
- [ ] Incorrect relink target is rejected.
- [ ] Re-adding a deleted event does not resurrect stale review state.

## Performance
- [ ] Startup remains within the accepted PR1 baseline.
- [ ] 100+ image event loads progressively and remains responsive.
- [ ] Already-viewed previews reuse cache.
- [ ] Repeated navigation does not show an obvious unbounded memory regression.

## Automated gate
- [ ] Backend PR1 tests green on the final merge-candidate HEAD.
- [ ] TypeScript check green on the final merge-candidate HEAD.
- [ ] Next production build green on the final merge-candidate HEAD.
- [ ] Tauri/Rust cargo check green on the final merge-candidate HEAD.

## Research isolation
- [x] J0/J1 JPEG experiments live under `backend/training_lab/`.
- [x] Synthetic/real-style smoke results are labeled non-production and non-quality claims.
- [x] Locked Test audit requires an explicit unlock and does not refit candidate weights.
- [x] Research tooling does not change the production claim that PR1 has no trained JPEG product model.

## Merge condition
Do not merge PR #1 until the final automated gate is green and the remaining unchecked manual merge-smoke items above are either passed or explicitly documented as out of PR1 scope with a reason.
