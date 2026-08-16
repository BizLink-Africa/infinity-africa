import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const dirname = path.dirname(fileURLToPath(import.meta.url));

// Minimal, isolated from the Next.js build — only used by `npx vitest run`.
// Component-level existence/rendering assertions only (no server, no real
// network); jsdom is enough, nothing here needs a real browser.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    // Default `forks` pool hangs waiting for the worker to respond in this
    // Windows environment; `threads` starts reliably.
    pool: "threads",
    // React Testing Library only auto-registers its afterEach(cleanup) when
    // it detects global test hooks — without this, DOM from earlier `it()`
    // blocks in the same file leaks into later ones.
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(dirname, "./src"),
    },
  },
});
