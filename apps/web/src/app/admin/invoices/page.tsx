import { redirect } from "next/navigation";

export default function AdminInvoicesRedirect() {
  redirect("/super-admin/invoices");
}
