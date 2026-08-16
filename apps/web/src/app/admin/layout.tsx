import { requireSuperAdmin } from "@/lib/supabase/protected-route";
import { AdminShell } from "@/components/admin/admin-shell";
import { listAdminNotifications } from "@/lib/admin/live-api";

export const metadata = {
  title: "Super Admin | Infinity Africa",
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!process.env.__PORTAL_UI_PREVIEW__) await requireSuperAdmin();

  const notifications = await listAdminNotifications();
  return <AdminShell notificationCount={notifications.filter((n) => !n.is_read).length}>{children}</AdminShell>;
}
