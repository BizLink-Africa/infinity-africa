import { redirect } from "next/navigation";

import { requireCurrentUser } from "@/lib/auth/current-user";
import { getOnboardingStatus } from "@/lib/onboarding/api";
import { InvoicesView } from "@/components/merchant/invoices-view";
import { PortalShell } from "@/components/portal/portal-shell";

export const metadata = {
  title: "Invoices | Infinity Africa",
};

export default async function InvoicesPage() {
  await requireCurrentUser("/merchant/login");

  const onboarding = await getOnboardingStatus();
  if (!onboarding || onboarding.next_path === "/onboarding") {
    redirect("/onboarding");
  }

  return (
    <PortalShell>
      <InvoicesView />
    </PortalShell>
  );
}
