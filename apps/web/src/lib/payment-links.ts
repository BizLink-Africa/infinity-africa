import "server-only";

export type PaymentLinkStatus = "ACTIVE" | "EXPIRED" | "CANCELLED" | "PAID";

export interface PublicPaymentLink {
  merchant_name: string;
  amount: string;
  currency: string;
  description: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  expires_at: string | null;
  allowed_payment_methods: string[];
  status: PaymentLinkStatus;
  success_redirect_url: string | null;
  failure_redirect_url: string | null;
}

export interface PublicCollectionReceipt {
  collection_id: string;
  merchant_name: string;
  amount: string;
  currency: string;
  description: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  method: string;
  merchant_reference: string | null;
  provider_reference: string | null;
  provider_transid: string | null;
  channel: string | null;
  completed_at: string | null;
}

/** Mirrors apps/api's {success, data} / {success, error} envelope. */
interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

/**
 * Fetches the public checkout view of a payment link from apps/api. Returns
 * null for anything that isn't a normal 200 (unknown slug -> 404; a
 * network/server error) — the page renders the same "link unavailable"
 * state either way, since there's nothing more specific to tell a customer
 * in either case.
 */
export async function fetchPublicPaymentLink(slug: string): Promise<PublicPaymentLink | null> {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body: ApiEnvelope<PublicPaymentLink> = await response.json();
    return body.success && body.data ? body.data : null;
  } catch {
    return null;
  }
}

/**
 * Fetches a payment receipt — only ever succeeds once the backend has
 * confirmed the collection genuinely reached "successful" (a 409 for
 * anything else comes back as null here, same as an unknown slug/id).
 * Every field returned is Selcom's own already-captured data; nothing
 * is generated client-side.
 */
export async function fetchPublicCollectionReceipt(
  slug: string,
  collectionId: string,
): Promise<PublicCollectionReceipt | null> {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/collections/${collectionId}/receipt`,
      { cache: "no-store" },
    );

    if (!response.ok) {
      return null;
    }

    const body: ApiEnvelope<PublicCollectionReceipt> = await response.json();
    return body.success && body.data ? body.data : null;
  } catch {
    return null;
  }
}
