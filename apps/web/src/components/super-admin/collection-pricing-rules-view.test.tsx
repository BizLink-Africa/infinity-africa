import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CollectionPricingRuleRow, Merchant } from "@/lib/admin/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/admin/live-actions", () => ({
  createMerchantCollectionPricingRuleAction: vi.fn(),
  createPlatformFallbackCollectionPricingRuleAction: vi.fn(),
  updateCollectionPricingRuleAction: vi.fn(),
  deactivateCollectionPricingRuleAction: vi.fn(),
  activateCollectionPricingRuleAction: vi.fn(),
}));

const merchant: Merchant = {
  merchant_id: "merchant-1",
  merchant_code: "27048391",
  business_name: "Juma Traders Ltd",
  owner_name: null,
  email: "juma@example.com",
  contact_phone: null,
  nature_of_business: null,
  physical_address: null,
  account_status: "active",
  kyc_status: "verified",
  api_access_suspended: false,
  production_api_eligible: true,
  available_balance: "0",
  created_at: "2026-08-01T00:00:00Z",
};

const platformRule: CollectionPricingRuleRow = {
  id: "rule-1",
  merchant_id: null,
  channel: null,
  percentage_fee: "0.800",
  flat_fee: "0.00",
  minimum_fee: null,
  maximum_fee: null,
  effective_from: "2026-08-01T00:00:00Z",
  effective_to: null,
  is_active: true,
  label: "Platform default",
  notes: null,
  created_by: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

describe("CollectionPricingRulesView", () => {
  it("shows the required helper text, a merchant selector, and the Add Collection Pricing Rule action", async () => {
    const { CollectionPricingRulesView } = await import("./collection-pricing-rules-view");
    render(
      <CollectionPricingRulesView
        merchants={[merchant]}
        platformRules={[platformRule]}
        selectedMerchantId={null}
        merchantRules={[]}
      />,
    );

    expect(
      screen.getByText("These fees apply to collection transactions only. Withdrawals do not charge merchant fees during MVP."),
    ).toBeInTheDocument();
    expect(screen.getByText("Collection pricing is negotiated separately with each merchant/customer.")).toBeInTheDocument();
    expect(screen.getByText("Juma Traders Ltd")).toBeInTheDocument();
    expect(screen.getAllByText("Add Collection Pricing Rule").length).toBeGreaterThan(0);
    expect(screen.getByText("Platform default", { exact: false })).toBeInTheDocument();
  });

  it("surfaces a failed save's error message instead of doing nothing", async () => {
    const { updateCollectionPricingRuleAction } = await import("@/lib/admin/live-actions");
    vi.mocked(updateCollectionPricingRuleAction).mockResolvedValue({
      error: "maximum_fee must be greater than or equal to minimum_fee",
    });

    const { CollectionPricingRulesView } = await import("./collection-pricing-rules-view");
    render(
      <CollectionPricingRulesView
        merchants={[merchant]}
        platformRules={[platformRule]}
        selectedMerchantId={null}
        merchantRules={[]}
      />,
    );

    fireEvent.click(screen.getByTitle("Edit"));
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() =>
      expect(screen.getByText("maximum_fee must be greater than or equal to minimum_fee")).toBeInTheDocument(),
    );
    expect(updateCollectionPricingRuleAction).toHaveBeenCalledTimes(1);
  });

  it("shows an Activate action for a deactivated rule, not a second Deactivate", async () => {
    const inactiveRule: CollectionPricingRuleRow = { ...platformRule, is_active: false };
    const { CollectionPricingRulesView } = await import("./collection-pricing-rules-view");
    render(
      <CollectionPricingRulesView
        merchants={[merchant]}
        platformRules={[inactiveRule]}
        selectedMerchantId={null}
        merchantRules={[]}
      />,
    );

    expect(screen.getByTitle("Activate")).toBeInTheDocument();
    expect(screen.queryByTitle("Deactivate")).not.toBeInTheDocument();
  });
});
