// /pay/[slug] — a merchant's permanent public Pay by Link checkout page.
// Deliberately noindex for MVP (feature brief's own "decide carefully...
// noindex may be safer" guidance): being publicly reachable by anyone with
// the link is the point, but a search engine caching a live checkout page
// (merchant name, amount fields, QR code) adds exposure with no real SEO
// upside. Revisit if the business wants these indexed later — remove this
// layout (or override with `robots: { index: true }` in a nested layout)
// rather than editing the page components themselves.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function PayLayout({ children }: { children: React.ReactNode }) {
  return children;
}
