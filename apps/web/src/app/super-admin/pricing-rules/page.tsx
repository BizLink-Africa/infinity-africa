import { PageHeader } from "@/components/portal/page-header";
import { PricingRulesView } from "@/components/super-admin/pricing-rules-view";
import { listAdminMerchants, listPlatformFallbackPricingRules, listPricingRulesForMerchant } from "@/lib/admin/live-api";

export const metadata = {
  title: "Pricing Rules | Infinity Africa Super Admin",
};

export default async function SuperAdminPricingRulesPage({
  searchParams,
}: {
  searchParams: Promise<{ merchant_id?: string }>;
}) {
  const { merchant_id: selectedMerchantId } = await searchParams;

  const [merchants, platformRules, merchantRules] = await Promise.all([
    listAdminMerchants(),
    listPlatformFallbackPricingRules(),
    selectedMerchantId ? listPricingRulesForMerchant(selectedMerchantId) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Pricing Rules"
        description="Configure platform-wide fallback fees and negotiated per-merchant withdrawal pricing."
      />
      <PricingRulesView
        merchants={merchants}
        platformRules={platformRules}
        selectedMerchantId={selectedMerchantId ?? null}
        merchantRules={merchantRules}
      />
    </div>
  );
}
