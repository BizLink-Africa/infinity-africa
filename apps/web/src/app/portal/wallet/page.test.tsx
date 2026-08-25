import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WalletLedgerEntry } from "@/lib/portal/types";

const getAvailableBalance = vi.fn();
const listWalletLedger = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  getAvailableBalance: (...args: unknown[]) => getAvailableBalance(...args),
  listWalletLedger: (...args: unknown[]) => listWalletLedger(...args),
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
});
