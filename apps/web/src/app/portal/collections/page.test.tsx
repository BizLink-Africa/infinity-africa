import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CollectionMethod } from "@infinity/shared";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Collection, HostedCheckoutCollection } from "@/lib/portal/types";

const listCollections = vi.fn();
const createHostedCheckoutCollection = vi.fn();
const refreshCollectionStatus = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listCollections: (...args: unknown[]) => listCollections(...args),
  createHostedCheckoutCollection: (...args: unknown[]) => createHostedCheckoutCollection(...args),
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
    method: CollectionMethod.HOSTED_CHECKOUT,
    amount: "1000.00",
    currency: "TZS",
    customer_phone: "255762474101",
    status: "processing",
    provider: "selcom",
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

function hostedCheckoutCollection(overrides: Partial<HostedCheckoutCollection> = {}): HostedCheckoutCollection {
  return { ...collection({}), payment_gateway_url: "https://tza.selcom.online/paymentgw/checkout/abc", ...overrides };
}

beforeEach(() => {
  vi.clearAllMocks();
  listCollections.mockResolvedValue([]);
});

describe("Merchant portal CollectionsPage — Request Collection form", () => {
  it("does not render a channel/method selector", async () => {
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    expect(screen.queryByLabelText("Channel")).not.toBeInTheDocument();
    expect(screen.queryByText("USSD Push")).not.toBeInTheDocument();
    expect(screen.queryByText("Allowed Payment Channels")).not.toBeInTheDocument();
  });

  it("shows the hosted-checkout explanation copy", async () => {
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    expect(
      screen.getByText("Secure Selcom hosted checkout — the customer chooses their payment method on checkout."),
    ).toBeInTheDocument();
  });

  it("submits amount/customer details without a method field, then shows Open checkout / Copy checkout link", async () => {
    createHostedCheckoutCollection.mockResolvedValue(hostedCheckoutCollection());
    const { default: CollectionsPage } = await import("./page");
    render(<CollectionsPage />);

    fireEvent.change(screen.getByLabelText("Customer Name"), { target: { value: "Grace" } });
    fireEvent.change(screen.getByLabelText("Amount in TZS"), { target: { value: "5000" } });
    fireEvent.click(screen.getByRole("button", { name: /Request Collection/ }));

    await waitFor(() =>
      expect(createHostedCheckoutCollection).toHaveBeenCalledWith(
        expect.objectContaining({ customer_name: "Grace", amount: "5000" }),
      ),
    );
    expect(createHostedCheckoutCollection.mock.calls[0][0]).not.toHaveProperty("method");

    const openCheckout = await screen.findByRole("link", { name: /Open checkout/ });
    expect(openCheckout).toHaveAttribute("href", "https://tza.selcom.online/paymentgw/checkout/abc");
    expect(screen.getByRole("button", { name: /Copy checkout link/ })).toBeInTheDocument();
  });
});

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
