import { redirect } from "next/navigation";

export default function AdminAuditLogsRedirect() {
  redirect("/super-admin/audit-logs");
}
