import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { PayByLinkView } from "@/components/merchant/pay-by-link-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "Pay by Link | Infinity Africa",
};

export default async function PayByLinkPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <PayByLinkView />
    </PortalShell>
  );
}
