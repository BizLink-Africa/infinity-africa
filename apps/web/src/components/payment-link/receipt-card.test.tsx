import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PublicCollectionReceipt } from "@/lib/payment-links";

import { ReceiptCard } from "./receipt-card";

const receipt: PublicCollectionReceipt = {
  collection_id: "11111111-1111-1111-1111-111111111111",
  merchant_name: "Salome Mponeja Shop",
  amount: "2500.00",
  currency: "TZS",
  description: "Order #482",
  customer_name: "Grace",
  customer_phone: "255747730270",
  method: "Mobile Money Push",
  provider_reference: "S20690471578",
  provider_transid: "TXN-ABC123",
  channel: "TIGOPESA",
  completed_at: "2026-08-24T10:15:00Z",
};

describe("ReceiptCard", () => {
  it("shows only Selcom-confirmed values, never generated ones", () => {
    render(<ReceiptCard receipt={receipt} />);

    expect(screen.getByText("TZS 2,500.00")).toBeInTheDocument();
    expect(screen.getByText("Salome Mponeja Shop")).toBeInTheDocument();
    expect(screen.getByText("Order #482")).toBeInTheDocument();
    expect(screen.getByText("Mobile Money Push")).toBeInTheDocument();
    expect(screen.getByText("TIGOPESA")).toBeInTheDocument();
    expect(screen.getByText("S20690471578")).toBeInTheDocument();
    expect(screen.getByText("TXN-ABC123")).toBeInTheDocument();
    expect(screen.getByText(receipt.collection_id)).toBeInTheDocument();
  });

  it("omits optional rows entirely when the backend didn't return them", () => {
    render(<ReceiptCard receipt={{ ...receipt, description: null, channel: null, provider_transid: null }} />);

    expect(screen.queryByText("Order #482")).not.toBeInTheDocument();
    expect(screen.queryByText("Channel")).not.toBeInTheDocument();
    expect(screen.queryByText("Transaction ID")).not.toBeInTheDocument();
  });

  it("the Download Receipt button triggers the browser print dialog", () => {
    const printSpy = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<ReceiptCard receipt={receipt} />);

    screen.getByRole("button", { name: "Download Receipt" }).click();

    expect(printSpy).toHaveBeenCalledTimes(1);
    printSpy.mockRestore();
  });
});
