// Auth pages are never a useful search result and shouldn't be indexed.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
