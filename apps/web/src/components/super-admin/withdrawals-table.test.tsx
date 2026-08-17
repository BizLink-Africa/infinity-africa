import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AdminWithdrawalRow } from "@/lib/admin/types";

vi.mock("@/lib/admin/live-actions", () => ({
  approveWithdrawalAction: vi.fn(),
  rejectWithdrawalAction: vi.fn(),
  requestInfoWithdrawalAction: vi.fn(),
  refreshWithdrawalStatusAction: vi.fn(),
  reconcilePendingWithdrawalsAction: vi.fn(),
}));

const pendingRow: AdminWithdrawalRow = {
  withdrawal_id: "wd-1",
  merchant_id: "merchant-1",
  merchant_name: "Juma Traders Ltd",
  method: "MOBILE_MONEY",
  amount: "100000.00",
  currency: "TZS",
  destination: "Jane Doe",
  destination_code: "MPESA",
  destination_identifier: "+255700000000",
  status: "PENDING_ADMIN_APPROVAL",
  requires_approval: true,
  provider_reference: null,
  total_charges: "1800.00",
  total_reserved_amount: "101800.00",
  recipient_net_amount: "100000.00",
  pricing_rule_id: null,
  rejection_reason: null,
  admin_status_reason: null,
  created_at: "2026-08-13T09:12:00Z",
};

describe("WithdrawalsTable", () => {
  it("shows Approve, Reject, and Request Info in the approval queue", async () => {
    const { WithdrawalsTable } = await import("./withdrawals-table");
    render(<WithdrawalsTable rows={[pendingRow]} queue={[pendingRow]} />);

    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
    expect(screen.getByText("Request Info")).toBeInTheDocument();
  });
});
