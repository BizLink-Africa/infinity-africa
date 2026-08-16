import { Card } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { OnboardingTable } from "@/components/super-admin/onboarding-table";
import { listOnboardingSubmissions } from "@/lib/onboarding/api";

export const metadata = {
  title: "Onboarding Requests | Infinity Africa",
};

export default async function SuperAdminOnboardingPage() {
  const rows = await listOnboardingSubmissions();

  return (
    <div className="space-y-8">
      <PageHeader title="Onboarding Requests" description="Review merchant onboarding submissions and manage verification." />
      <Card padded={false}>
        <OnboardingTable rows={rows} />
      </Card>
    </div>
  );
}
