import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    // Rust/Tauri build output is generated and can contain binary-backed JS assets.
    "src-tauri/target/**",
    "next-env.d.ts",
  ]),
  {
    // These effects intentionally synchronize UI state with navigation,
    // network requests, and Blob URL lifecycles. Keep this exception scoped
    // to the existing components rather than disabling the rule globally.
    files: [
      "src/features/darkroom/DarkroomScreen.tsx",
      "src/features/darkroom/JpegRenderedPreview.tsx",
      "src/features/events/EventsScreen.tsx",
      "src/features/gallery/GalleryScreen.tsx",
      "src/features/profile/ProfileScreen.tsx",
      "src/features/review/CameraPreview.tsx",
    ],
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
  {
    // These components render authenticated Blob/object URLs or in-memory
    // data URLs from the local engine; Next Image optimization is not
    // applicable to that source.
    files: [
      "src/features/darkroom/JpegRenderedPreview.tsx",
      "src/features/review/CameraPreview.tsx",
      "src/features/learning-intake/LearningIntakeScreen.tsx",
    ],
    rules: {
      "@next/next/no-img-element": "off",
    },
  },
]);

export default eslintConfig;
