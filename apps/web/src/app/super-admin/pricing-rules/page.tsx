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
        title="Withdrawal Pricing Rules (Inactive)"
        description="These rules no longer charge merchants — withdrawal fees were removed platform-wide. Infinity Africa now earns fees from collections only."
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
