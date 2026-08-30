import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FeeBreakdown } from "@/lib/portal/types";

// MVP policy (2026-08-31): withdrawals never charge a merchant fee — the
// backend always returns a zero breakdown now (see
// apps/api/app/services/withdrawals/fee_calculator.py). This mock mirrors
// that real shape rather than a hypothetical fee-bearing one.
const breakdown: FeeBreakdown = {
  withdrawal_amount: "100000.00",
  processor_charge: "0",
  infinity_fee: "0",
  percentage_fee: "0",
  flat_fee: "0",
  total_charges: "0",
  total_reserved_amount: "100000.00",
  recipient_net_amount: "100000.00",
  channel: "SELCOM_PESA",
  destination_code: "SELCOM",
  pricing_rule_id: null,
  pricing_rule_label: null,
  processor_fee_pass_through: false,
  is_platform_fallback: false,
};

const calculateWithdrawalCharges = vi.fn().mockResolvedValue(breakdown);

vi.mock("@/lib/portal/api", () => ({
  listDisbursements: vi.fn().mockResolvedValue([]),
  getAvailableBalance: vi.fn().mockResolvedValue("500000.00"),
  calculateWithdrawalCharges,
  createDisbursement: vi.fn(),
  InsufficientBalanceError: class InsufficientBalanceError extends Error {},
}));

describe("WithdrawalsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a Check Balance button", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    render(<WithdrawalsView />);

    await waitFor(() => expect(screen.getByText("Check Balance")).toBeInTheDocument());
  });

  it("shows the withdrawal amount and a no-fee notice, never a fee/charge breakdown", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    render(<WithdrawalsView />);

    fireEvent.change(screen.getByPlaceholderText("+255 7XX XXX XXX or account no."), {
      target: { value: "+255700000000" },
    });
    fireEvent.change(screen.getByPlaceholderText("500,000"), { target: { value: "100000" } });
    fireEvent.click(screen.getByText("Check Balance"));

    await waitFor(() => expect(calculateWithdrawalCharges).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByText("No merchant withdrawal fee — you receive the full amount.")).toBeInTheDocument(),
    );

    // The old fee-breakdown rows must be gone entirely — this is the
    // point of the MVP pricing change, not just an added message.
    expect(screen.queryByText("Infinity Africa Fee")).not.toBeInTheDocument();
    expect(screen.queryByText("Processor Charge")).not.toBeInTheDocument();
    expect(screen.queryByText("Total Charges")).not.toBeInTheDocument();
    expect(screen.queryByText("Total to Be Deducted")).not.toBeInTheDocument();
    expect(screen.queryByText("Recipient Receives")).not.toBeInTheDocument();
    expect(screen.queryByText(/pricing rule applied/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/platform fallback/i)).not.toBeInTheDocument();
  });

  it("never shows the literal word 'Disbursement' in merchant-facing text", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    const { container } = render(<WithdrawalsView />);

    await waitFor(() => expect(screen.getByText("Withdrawals")).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/Disbursement/i);
  });
});
