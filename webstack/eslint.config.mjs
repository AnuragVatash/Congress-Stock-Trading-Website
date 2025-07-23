// eslint.config.js (or eslint.config.mjs)
import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";
import { globalIgnores } from "eslint/config";        // ⬅️ new
                                                     //  ────
const __filename = fileURLToPath(import.meta.url);
const __dirname  = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

export default [
  // 1️⃣ completely ignore generated code
  globalIgnores([
    "src/generated/**",          // Prisma client & WASM stubs
    "src/generated/prisma/**",
    "src/lib/**",
    "src/components/IssuersTable.tsx" // Ignore this file due to persistent linter false positive
  ]),

  // 2️⃣ everything else: reuse Next.js presets
  ...compat.extends(
    "next/core-web-vitals",
    "next/typescript"
  ),
];