// Public one-off payment-link checkout pages — ephemeral, transaction-
// specific, never useful as a search result.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function PaymentLinksLayout({ children }: { children: React.ReactNode }) {
  return children;
}
