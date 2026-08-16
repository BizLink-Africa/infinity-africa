import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { WithdrawalsView } from "@/components/merchant/withdrawals-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "Withdrawals | Infinity Africa",
};

export default async function WithdrawalsPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <WithdrawalsView />
    </PortalShell>
  );
}
