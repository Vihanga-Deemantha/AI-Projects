import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = defineConfig([
  ...nextVitals,
  // Next's preset leaves `no-undef` off, so a name that exists only in another component (a child reading
  // its parent's state) passes lint and the build and then crashes the page when it is opened.
  { files: ["**/*.{js,mjs,cjs}"], rules: { "no-undef": "error" } },
  // The preset knows the browser and Node globals for modules, but not for CommonJS build scripts.
  {
    files: ["**/*.cjs"],
    languageOptions: { globals: { __dirname: "readonly", console: "readonly", process: "readonly" } },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
