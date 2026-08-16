import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { ApiKeysView } from "@/components/merchant/api-keys-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "API Keys | Infinity Africa",
};

export default async function ApiKeysPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <ApiKeysView />
    </PortalShell>
  );
}
