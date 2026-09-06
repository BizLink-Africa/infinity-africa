// Merchant onboarding is only ever reached by an already-signed-up user
// completing their business profile — not a page anyone should land on
// from a search result.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
