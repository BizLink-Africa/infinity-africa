import { requireCurrentUser } from "@/lib/auth/current-user";
import { requireVerifiedMerchant } from "@/lib/onboarding/guard";
import { WithdrawalsView } from "@/components/merchant/withdrawals-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "Withdrawals | Infinity Africa",
};

export default async function WithdrawalsPage() {
  await requireCurrentUser("/merchant/login");
  await requireVerifiedMerchant();

  return (
    <PortalShell>
      <WithdrawalsView />
    </PortalShell>
  );
}
