import { Suspense } from "react";

import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { ApiCredentialsTabs } from "@/components/merchant/api-credentials-tabs";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "API Credentials | Infinity Africa",
};

export default async function ApiCredentialsPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <Suspense fallback={null}>
        <ApiCredentialsTabs />
      </Suspense>
    </PortalShell>
  );
}
