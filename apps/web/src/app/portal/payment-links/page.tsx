import { redirect } from "next/navigation";

export default function PortalPaymentLinksRedirect() {
  redirect("/merchant/payment-links");
}
