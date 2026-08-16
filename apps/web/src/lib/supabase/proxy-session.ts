import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { isSupabaseConfigured } from "@/lib/auth/supabase-status";

/**
 * Refreshes the Supabase session cookie on every request, per the
 * @supabase/ssr Next.js pattern — this used to live in middleware.ts; Next
 * 16 renamed that file to proxy.ts (see apps/web/src/proxy.ts).
 *
 * Must fail open: this repo's .env.local currently points at an unreachable
 * local Supabase instance (http://localhost:54321, nothing listening), so
 * an unguarded call here would hang/error on every single page load.
 */
export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({ request });

  if (!isSupabaseConfigured()) {
    return response;
  }

  try {
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return request.cookies.getAll();
          },
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
            response = NextResponse.next({ request });
            cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
          },
        },
      },
    );

    await supabase.auth.getUser();
  } catch {
    // Connectivity failure (or any other Supabase error) — fail open and
    // let the request through unmodified.
  }

  return response;
}
