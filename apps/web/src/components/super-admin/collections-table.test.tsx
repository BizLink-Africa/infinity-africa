import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AdminCollectionRow } from "@/lib/admin/types";

const refreshAdminCollectionStatusClient = vi.fn();

vi.mock("@/lib/admin/refresh-collection-status-client", () => ({
  refreshAdminCollectionStatusClient: (...args: unknown[]) => refreshAdminCollectionStatusClient(...args),
}));

function row(overrides: Partial<AdminCollectionRow>): AdminCollectionRow {
  return {
    collection_id: "col-1",
    merchant_id: "merchant-1",
    merchant_name: "Juma Traders Ltd",
    method: "STK_PUSH",
    amount: "1000.00",
    currency: "TZS",
    phone: "255762474101",
    provider_reference: "S123",
    status: "processing",
    created_at: "2026-08-22T21:20:00Z",
    order_id: "ORD-1",
    provider_transid: "TXN-1",
    channel: null,
    provider_payment_status: null,
    failure_reason: null,
    ...overrides,
  };
}

describe("CollectionsTable", () => {
  it("shows Refresh status for a processing collection", async () => {
    const { CollectionsTable } = await import("./collections-table");
    render(<CollectionsTable collections={[row({ status: "processing" })]} />);

    expect(screen.getByRole("button", { name: "Refresh status" })).toBeInTheDocument();
  });

  it("does not show Refresh status for a successful collection", async () => {
    const { CollectionsTable } = await import("./collections-table");
    render(<CollectionsTable collections={[row({ status: "successful" })]} />);

    expect(screen.queryByRole("button", { name: "Refresh status" })).not.toBeInTheDocument();
  });

  it("does not show Refresh status for a failed collection", async () => {
    const { CollectionsTable } = await import("./collections-table");
    render(<CollectionsTable collections={[row({ status: "failed", failure_reason: "Rejected by customer" })]} />);

    expect(screen.queryByRole("button", { name: "Refresh status" })).not.toBeInTheDocument();
    expect(screen.getByText("Rejected by customer")).toBeInTheDocument();
  });

  it("calls refreshAdminCollectionStatusClient with this row's collection_id, then updates the row in place", async () => {
    refreshAdminCollectionStatusClient.mockResolvedValue(row({ status: "successful", collection_id: "col-1" }));
    const { CollectionsTable } = await import("./collections-table");
    render(<CollectionsTable collections={[row({ status: "processing", collection_id: "col-1" })]} />);

    fireEvent.click(screen.getByRole("button", { name: "Refresh status" }));

    await waitFor(() => expect(refreshAdminCollectionStatusClient).toHaveBeenCalledWith("col-1"));
    expect(await screen.findByText("Payment completed")).toBeInTheDocument();
  });
});
