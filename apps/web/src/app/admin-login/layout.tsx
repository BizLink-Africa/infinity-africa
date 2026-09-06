// Super Admin's own login page — never a useful search result, and no
// reason to advertise its existence to a crawler either.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function AdminLoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
