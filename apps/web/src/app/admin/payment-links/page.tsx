import { redirect } from "next/navigation";

export default function AdminPaymentLinksRedirect() {
  redirect("/super-admin/payment-links");
}
