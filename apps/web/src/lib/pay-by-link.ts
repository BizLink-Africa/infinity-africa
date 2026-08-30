import "server-only";

export interface PublicPayByLink {
  display_name: string;
  description: string | null;
  is_active: boolean;
}

/** Mirrors apps/api's {success, data} / {success, error} envelope — same
 * shape lib/payment-links.ts already declares its own private copy of. */
interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

/**
 * Fetches the public view of a merchant's permanent Pay by Link page.
 * Returns null for anything that isn't a normal 200 (unknown slug -> 404;
 * a network/server error) — same "return null, let the caller decide
 * what to show" convention as fetchPublicPaymentLink. The resolver page
 * (app/pay/[slug]/page.tsx) tries fetchPublicPaymentLink FIRST and only
 * falls back to this when that returns null, so an existing generated
 * payment link's slug is never shadowed by a permanent Pay by Link page.
 */
export async function fetchPublicPayByLink(slug: string): Promise<PublicPayByLink | null> {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/pay-by-link/${slug}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body: ApiEnvelope<PublicPayByLink> = await response.json();
    return body.success && body.data ? body.data : null;
  } catch {
    return null;
  }
}
