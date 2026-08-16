/**
 * Whether Supabase Auth is actually usable right now. The env vars can be
 * *present* but still point at nothing real — e.g. this repo's .env.local
 * ships local Supabase CLI placeholders (http://localhost:54321 /
 * local-dev-placeholder-key) with no instance actually listening. Treat
 * those as "not configured" so the app falls back to the mock auth store
 * instead of hanging on unreachable requests.
 *
 * This is a fast static pre-check only — callers must still wrap the real
 * Supabase call in try/catch, since a URL that looks real can still be
 * unreachable at request time (paused project, network issue, etc).
 */

const KNOWN_PLACEHOLDER_URLS = new Set(["http://localhost:54321"]);
const KNOWN_PLACEHOLDER_KEYS = new Set(["local-dev-placeholder-key"]);

export function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) return false;
  if (KNOWN_PLACEHOLDER_URLS.has(url)) return false;
  if (KNOWN_PLACEHOLDER_KEYS.has(anonKey)) return false;

  return true;
}

/**
 * True if an error thrown from a Supabase Auth call represents a real
 * rejection from a reachable server (bad credentials, duplicate email,
 * weak password per Supabase's own policy, etc) rather than a connectivity
 * failure. Only connectivity failures should fall back to the mock store —
 * a real rejection must surface to the user as-is, otherwise a duplicate
 * signup attempt would silently succeed against the mock store instead of
 * correctly failing.
 */
export function isKnownAuthRejection(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const name = "name" in error ? String((error as { name?: unknown }).name) : "";
  const status = "status" in error ? Number((error as { status?: unknown }).status) : undefined;

  if (name === "AuthRetryableFetchError") return false;
  if (name === "AuthUnknownError") return false;
  if (status !== undefined && status >= 500) return false;

  // Anything else with an HTTP-ish status (400/401/422/etc) is a real
  // rejection from a server that did respond.
  return status !== undefined;
}
