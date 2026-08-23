import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Transaction } from "@/lib/portal/types";

const listTransactions = vi.fn();
const listMyRiskAlerts = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listTransactions: (...args: unknown[]) => listTransactions(...args),
  listMyRiskAlerts: (...args: unknown[]) => listMyRiskAlerts(...args),
}));

function transaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: "txn-1",
    merchant_id: "merchant-1",
    reference: "TXN-20260822-E7803AE4",
    provider_reference: null,
    type: "collection",
    method: "DYNAMIC_QR",
    collection_id: "col-1",
    disbursement_id: null,
    gross_amount: "2000.00",
    fee_amount: "30.00",
    net_amount: "1970.00",
    currency: "TZS",
    status: "pending",
    created_at: "2026-08-23T01:37:00Z",
    ...overrides,
  };
}

describe("Merchant portal TransactionsPage — Export CSV", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMyRiskAlerts.mockResolvedValue([]);
    if (!URL.createObjectURL) URL.createObjectURL = vi.fn();
    if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  });

  it("disables the Export CSV button when there are no transactions", async () => {
    listTransactions.mockResolvedValue([]);
    const { default: TransactionsPage } = await import("./page");
    render(<TransactionsPage />);

    await waitFor(() => expect(listTransactions).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: /Export CSV/ })).toBeDisabled();
  });

  it("downloads a CSV containing every visible transaction when clicked", async () => {
    listTransactions.mockResolvedValue([transaction()]);
    const { default: TransactionsPage } = await import("./page");
    render(<TransactionsPage />);

    const button = await screen.findByRole("button", { name: /Export CSV/ });
    await waitFor(() => expect(button).not.toBeDisabled());

    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreateElement(tag);
      if (tag === "a") el.click = clickSpy;
      return el;
    });

    fireEvent.click(button);

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('"Date","Type","Reference","Channel","Amount","Currency","Status"');
    expect(text).toContain("TXN-20260822-E7803AE4");
    expect(text).toContain("DYNAMIC_QR");
    expect(text).toContain("+2000.00");
    expect(clickSpy).toHaveBeenCalledTimes(1);

    createElementSpy.mockRestore();
  });
});
