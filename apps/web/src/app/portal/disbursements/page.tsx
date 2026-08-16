import { redirect } from "next/navigation";

export default function PortalDisbursementsRedirect() {
  redirect("/merchant/withdrawals");
}
