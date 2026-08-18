import { redirect } from "next/navigation";

export default function PortalInvoicesRedirect() {
  redirect("/merchant/invoices");
}
