# Learning UI consistency polish

This change adds a shared breadcrumbs component and a guarded installer for the user's locally installed premium JPEG and RAW UI.

The finished JPEG/RAW visual components were previously installed from local ZIP bundles and are not yet tracked on main. Replacing those from remote would risk destroying the approved local appearance, so this commit adds a narrowly scoped patch script instead.

Windows, from the repository root:
1. git pull --ff-only origin main
2. powershell -ExecutionPolicy Bypass -File .\scripts\apply-learning-ui-polish.ps1
3. cd frontend
4. npm.cmd run lint
5. npx.cmd tsc --noEmit
6. npm.cmd run build
7. npm.cmd run tauri dev

The installer validates all exact source anchors before modifying anything, makes backups in the user's TEMP folder, and touches only the profile card-group CSS, JPEG card arrow CSS, and the two installed training view TSX files.

Behavior changes:
- Remove only the surrounding shared learningSurface border and shadow so each profile training pane is independent.
- JPEG choice-card arrow points left as it does in RAW.
- RAW/JPEG breadcrumbs share a single accessible component with identical labels and styling. Only the RAW/JPEG final label differs.

Nothing changes in training APIs, RAW/JPEG logic, models, or image assets.

After local visual and frontend verification, reconcile the locally installed premium views and artwork with main in a separate explicit commit; never use git reset --hard or git clean -fd on the user's machine.
