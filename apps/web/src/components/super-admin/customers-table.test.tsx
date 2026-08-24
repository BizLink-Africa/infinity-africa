import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AdminCustomerPlatformRow } from "@/lib/admin/types";

import { CustomersTable } from "./customers-table";

function row(overrides: Partial<AdminCustomerPlatformRow>): AdminCustomerPlatformRow {
  return {
    id: "merchant-1:255700000001",
    merchant_id: "merchant-1",
    merchant_name: "Amani Traders",
    full_name: "Grace Mushi",
    phone: "255700000001",
    currency: "TZS",
    total_spent: "3000.00",
    transaction_count: 2,
    first_seen_at: "2026-08-01T10:00:00Z",
    last_transaction_at: "2026-08-20T10:00:00Z",
    ...overrides,
  };
}

describe("CustomersTable", () => {
  it("shows the customer's name, phone, merchant, and spend — never a fabricated name", () => {
    render(<CustomersTable rows={[row({})]} />);

    expect(screen.getByText("Grace Mushi")).toBeInTheDocument();
    expect(screen.getByText("255700000001")).toBeInTheDocument();
    expect(screen.getByText("Amani Traders")).toBeInTheDocument();
    expect(screen.getByText("TZS 3,000.00")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows a dash instead of a made-up name when none is known", () => {
    render(<CustomersTable rows={[row({ full_name: null })]} />);

    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("shows an empty state when there is no customer activity", () => {
    render(<CustomersTable rows={[]} />);

    expect(screen.getByText("No customer activity has been recorded yet.")).toBeInTheDocument();
  });
});
