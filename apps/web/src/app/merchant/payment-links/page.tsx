import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { PaymentLinksView } from "@/components/merchant/payment-links-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "Payment Links | Infinity Africa",
};

export default async function PaymentLinksPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <PaymentLinksView />
    </PortalShell>
  );
}
