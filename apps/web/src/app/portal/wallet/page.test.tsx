import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WalletLedgerEntry } from "@/lib/portal/types";

const getAvailableBalance = vi.fn();
const listWalletLedger = vi.fn();
const getMyMerchant = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  getAvailableBalance: (...args: unknown[]) => getAvailableBalance(...args),
  listWalletLedger: (...args: unknown[]) => listWalletLedger(...args),
  getMyMerchant: (...args: unknown[]) => getMyMerchant(...args),
}));

function ledgerEntry(overrides: Partial<WalletLedgerEntry> = {}): WalletLedgerEntry {
  return {
    id: "entry-1",
    transaction_id: "txn-1",
    date: "2026-08-23T01:37:00Z",
    description: "Merchant wallet credited (net of fee)",
    direction: "credit",
    amount: "1970.00",
    balance_before: "500.00",
    balance_after: "2470.00",
    ...overrides,
  };
}

describe("Merchant portal WalletPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAvailableBalance.mockResolvedValue("2470.00");
    getMyMerchant.mockResolvedValue({ merchant_code: "27048391" });
  });

  it("renders the opening and closing balance columns for a ledger entry", async () => {
    listWalletLedger.mockResolvedValue([ledgerEntry()]);
    const { default: WalletPage } = await import("./page");
    render(<WalletPage />);

    await waitFor(() => expect(listWalletLedger).toHaveBeenCalled());
    expect(screen.getByText("Opening Balance")).toBeInTheDocument();
    expect(screen.getByText("Closing Balance")).toBeInTheDocument();
    expect(screen.getByText("Transaction ID")).toBeInTheDocument();
  });

  it("shows an empty state, not an error, when there is no wallet activity yet", async () => {
    listWalletLedger.mockResolvedValue([]);
    const { default: WalletPage } = await import("./page");
    render(<WalletPage />);

    expect(await screen.findByText("No wallet activity yet.")).toBeInTheDocument();
  });

  it("shows the merchant's Merchant ID in the page header", async () => {
    listWalletLedger.mockResolvedValue([]);
    const { default: WalletPage } = await import("./page");
    render(<WalletPage />);

    expect(await screen.findByText("27048391")).toBeInTheDocument();
  });

  it("does not show the untracked Pending Clearance / Reserved Funds placeholder cards", async () => {
    listWalletLedger.mockResolvedValue([]);
    const { default: WalletPage } = await import("./page");
    render(<WalletPage />);

    await waitFor(() => expect(getAvailableBalance).toHaveBeenCalled());
    expect(screen.queryByText("Pending Clearance")).not.toBeInTheDocument();
    expect(screen.queryByText("Reserved Funds")).not.toBeInTheDocument();
    expect(screen.queryByText("Not tracked yet")).not.toBeInTheDocument();
    expect(screen.queryByText("Ready to withdraw")).not.toBeInTheDocument();
  });

  it("exports the wallet ledger to a downloadable CSV (Excel-openable)", async () => {
    if (!URL.createObjectURL) URL.createObjectURL = vi.fn();
    if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    listWalletLedger.mockResolvedValue([ledgerEntry()]);
    const { default: WalletPage } = await import("./page");
    render(<WalletPage />);

    const button = await screen.findByRole("button", { name: /Export to Excel/ });
    expect(button).not.toBeDisabled();

    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreateElement(tag);
      if (tag === "a") el.click = clickSpy;
      return el;
    });

    button.click();

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain(
      '"Date","Transaction ID","Description","Direction","Opening Balance","Amount","Closing Balance"',
    );
    expect(text).toContain("txn-1");
    expect(text).toContain("500.00");
    expect(text).toContain("2470.00");
    expect(clickSpy).toHaveBeenCalledTimes(1);

    createElementSpy.mockRestore();
  });
});
