import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CollectionMethod } from "@infinity/shared";
import { describe, expect, it, vi } from "vitest";

import type { Collection } from "@/lib/portal/types";

const listCollections = vi.fn();
const createCollection = vi.fn();
const refreshCollectionStatus = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listCollections: (...args: unknown[]) => listCollections(...args),
  createCollection: (...args: unknown[]) => createCollection(...args),
  refreshCollectionStatus: (...args: unknown[]) => refreshCollectionStatus(...args),
}));

function collection(overrides: Partial<Collection>): Collection {
  return {
    id: "col-1",
    merchant_id: "merchant-1",
    customer_id: null,
    payment_link_id: null,
    invoice_id: null,
    merchant_reference: null,
    method: CollectionMethod.STK_PUSH,
    amount: "1000.00",
    currency: "TZS",
    customer_phone: "255762474101",
    status: "processing",
    provider: "selcom_checkout",
    provider_reference: "S123",
    transaction_reference: null,
    message: null,
    expires_at: null,
    initiated_at: "2026-08-22T21:20:00Z",
    completed_at: null,
    created_at: "2026-08-22T21:20:00Z",
    updated_at: "2026-08-22T21:20:00Z",
    failure_reason: null,
    checkout_order_id: "order-1",
    provider_transid: "TXN-1",
    provider_resultcode: null,
    provider_result: null,
    provider_payment_status: null,
    channel: null,
    ...overrides,
  };
}

describe("Merchant portal CollectionsPage — refresh status", () => {
  it("shows Refresh status only for a processing collection", async () => {
    listCollections.mockResolvedValue([collection({ id: "col-1", status: "processing" })]);
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    expect(await screen.findByRole("button", { name: "Refresh status" })).toBeInTheDocument();
  });

  it("does not show Refresh status for a successful collection", async () => {
    listCollections.mockResolvedValue([collection({ id: "col-2", status: "successful" })]);
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    await waitFor(() => expect(listCollections).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Refresh status" })).not.toBeInTheDocument();
  });

  it("calls refreshCollectionStatus with this collection's id and reflects the completed result", async () => {
    listCollections.mockResolvedValue([collection({ id: "col-3", status: "processing" })]);
    refreshCollectionStatus.mockResolvedValue(collection({ id: "col-3", status: "successful" }));
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Refresh status" }));

    await waitFor(() => expect(refreshCollectionStatus).toHaveBeenCalledWith("col-3"));
    expect(await screen.findByText("Payment completed")).toBeInTheDocument();
  });

  it("shows the failure reason for a failed collection", async () => {
    listCollections.mockResolvedValue([
      collection({ id: "col-4", status: "failed", failure_reason: "Customer cancelled the prompt" }),
    ]);
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    expect(await screen.findByText("Customer cancelled the prompt")).toBeInTheDocument();
  });
});
