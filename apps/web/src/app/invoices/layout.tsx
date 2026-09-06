// Public one-off invoice payment pages — ephemeral, transaction-specific,
// never useful as a search result.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function InvoicesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
