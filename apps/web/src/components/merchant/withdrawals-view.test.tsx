import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FeeBreakdown } from "@/lib/portal/types";

const breakdown: FeeBreakdown = {
  withdrawal_amount: "100000.00",
  processor_charge: "300.00",
  infinity_fee: "1500.00",
  percentage_fee: "1000.00",
  flat_fee: "500.00",
  total_charges: "1800.00",
  total_reserved_amount: "101800.00",
  recipient_net_amount: "100000.00",
  channel: "SELCOM_PESA",
  destination_code: "SELCOM",
  pricing_rule_id: "rule-1",
  pricing_rule_label: "Negotiated rate",
  processor_fee_pass_through: true,
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

  it("shows a Calculate Charges button", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    render(<WithdrawalsView />);

    await waitFor(() => expect(screen.getByText("Calculate Charges")).toBeInTheDocument());
  });

  it("renders the fee breakdown after calculating charges", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    render(<WithdrawalsView />);

    fireEvent.change(screen.getByPlaceholderText("+255 7XX XXX XXX or account no."), {
      target: { value: "+255700000000" },
    });
    fireEvent.change(screen.getByPlaceholderText("500,000"), { target: { value: "100000" } });
    fireEvent.click(screen.getByText("Calculate Charges"));

    await waitFor(() => expect(calculateWithdrawalCharges).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Recipient Receives")).toBeInTheDocument());
    expect(screen.getByText("Negotiated rate", { exact: false })).toBeInTheDocument();
  });

  it("never shows the literal word 'Disbursement' in merchant-facing text", async () => {
    const { WithdrawalsView } = await import("./withdrawals-view");
    const { container } = render(<WithdrawalsView />);

    await waitFor(() => expect(screen.getByText("Withdrawals")).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/Disbursement/i);
  });
});
