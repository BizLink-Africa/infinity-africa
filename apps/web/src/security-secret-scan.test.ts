/**
 * MVP security-hardening pass: a regression guard that no backend secret's
 * env-var name ever appears anywhere in the frontend source tree — the
 * architectural invariant this whole app relies on is that apps/web never
 * touches these at all (only apps/api's app/config/settings.py does); a
 * manual `rg` secret scan (see docs/MVP_LAUNCH_CHECKLIST.md) catches this
 * once per audit, this test catches it on every CI run.
 *
 * Named exactly (not generic substrings like "SECRET"/"TOKEN"/"PASSWORD")
 * to avoid false positives on this codebase's own legitimate camelCase
 * identifiers (accessToken, resetToken, ...) — a case-sensitive
 * SCREAMING_SNAKE_CASE env-var name is what an accidentally-hardcoded or
 * accidentally-referenced secret would actually look like, matching how
 * the brief's own `rg` patterns are written.
 */
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = dirname(fileURLToPath(import.meta.url));
const THIS_FILE = fileURLToPath(import.meta.url);

// Every real secret field in apps/api/app/config/settings.py, as the
// SCREAMING_SNAKE_CASE env-var name pydantic-settings resolves it to.
const FORBIDDEN_NAMES = [
  "RESEND_API_KEY",
  "SUPABASE_SERVICE_ROLE_KEY",
  "SUPABASE_JWT_SECRET",
  "DATABASE_URL",
  "SELCOM_WEBHOOK_SECRET",
  "WEBHOOK_SECRET_ENCRYPTION_KEY",
  "SELCOM_API_KEY",
  "SELCOM_API_SECRET",
  "SELCOM_VENDOR_ID",
  "SELCOM_BUSINESS_API_KEY",
  "SELCOM_BUSINESS_PRIVATE_KEY_BASE64",
  "SELCOM_BUSINESS_ACCOUNT_NUMBER",
  "SELCOM_CHECKOUT_API_KEY",
  "SELCOM_CHECKOUT_API_SECRET",
  "SELCOM_CHECKOUT_PRIVATE_KEY_BASE64",
  "SELCOM_CHECKOUT_WEBHOOK_TEST_SECRET",
];

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, files);
    } else if (/\.(ts|tsx|js|jsx)$/.test(entry.name) && full !== THIS_FILE) {
      files.push(full);
    }
  }
  return files;
}

describe("no backend secret env-var name appears in the frontend source tree", () => {
  const files = walk(SRC_DIR);

  it("scans a non-trivial number of frontend source files", () => {
    // Sanity check on the scan itself — a walker that silently found
    // nothing would make every assertion below vacuously true.
    expect(files.length).toBeGreaterThan(50);
  });

  it.each(FORBIDDEN_NAMES)("%s never appears in apps/web/src", (name) => {
    const offenders = files.filter((file) => readFileSync(file, "utf8").includes(name));
    expect(offenders).toEqual([]);
  });

  it("never defines a NEXT_PUBLIC_ variant of any backend secret", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, "utf8");
      for (const name of FORBIDDEN_NAMES) {
        if (content.includes(`NEXT_PUBLIC_${name}`)) offenders.push(`${file}: NEXT_PUBLIC_${name}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
