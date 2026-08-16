import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/proxy-session";

// Next.js 16 renamed middleware.ts to proxy.ts — see
// node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md.
export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
