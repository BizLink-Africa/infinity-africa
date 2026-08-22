import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PublicPaymentLink } from "@/lib/payment-links";

import { PaymentForm } from "./payment-form";

const link: PublicPaymentLink = {
  merchant_name: "Test Merchant",
  amount: "25000.00",
  currency: "TZS",
  description: "Invoice for services",
  customer_name: null,
  customer_phone: null,
  expires_at: null,
  allowed_payment_methods: ["USSD_PUSH", "STK_PUSH", "SELCOM_PESA_PUSH", "DYNAMIC_QR"],
  status: "ACTIVE",
  success_redirect_url: null,
  failure_redirect_url: null,
};

describe("PaymentForm", () => {
  it("renders a button/option for every allowed payment method", () => {
    render(<PaymentForm slug="test-slug" link={link} />);

    expect(screen.getByText("Push USSD")).toBeInTheDocument();
    expect(screen.getByText("STK Push")).toBeInTheDocument();
    expect(screen.getByText("Push to Selcom Pesa")).toBeInTheDocument();
    expect(screen.getByText("Dynamic QR Code")).toBeInTheDocument();
  });

  it("only renders methods present in allowed_payment_methods", () => {
    render(<PaymentForm slug="test-slug" link={{ ...link, allowed_payment_methods: ["STK_PUSH"] }} />);

    expect(screen.getByText("STK Push")).toBeInTheDocument();
    expect(screen.queryByText("Dynamic QR Code")).not.toBeInTheDocument();
  });

  it("always renders the Mobile Money Push option, regardless of allowed_payment_methods", () => {
    render(<PaymentForm slug="test-slug" link={{ ...link, allowed_payment_methods: ["DYNAMIC_QR"] }} />);
    expect(screen.getByText("Pay with Mobile Money Push")).toBeInTheDocument();
  });
});

describe("PaymentForm — wallet push", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function selectWalletPush() {
    fireEvent.click(screen.getByText("Pay with Mobile Money Push"));
  }

  it("submits to /pay/wallet-push with a normalized phone and shows the backend's pending message", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          collection_id: "11111111-1111-1111-1111-111111111111",
          payment_status: "pending",
          message: "Payment request sent to your phone. Please approve using your PIN.",
        },
      }),
    });

    render(<PaymentForm slug="test-slug" link={link} />);
    selectWalletPush();
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747 730 270" } });
    fireEvent.click(screen.getByRole("button", { name: /Pay/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/public/payment-links/test-slug/pay/wallet-push");
    expect(init.headers["Idempotency-Key"]).toBeTruthy();
    expect(JSON.parse(init.body)).toEqual({ customer_phone: "0747 730 270" });

    await waitFor(() =>
      expect(screen.getByText("Payment request sent to your phone. Please approve using your PIN.")).toBeInTheDocument(),
    );
  });

  it("shows a failed state with the backend's message when the attempt fails outright", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          collection_id: "11111111-1111-1111-1111-111111111111",
          payment_status: "failed",
          message: "This payment attempt failed.",
        },
      }),
    });

    render(<PaymentForm slug="test-slug" link={link} />);
    selectWalletPush();
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    fireEvent.click(screen.getByRole("button", { name: /Pay/ }));

    await waitFor(() => expect(screen.getByText("This payment attempt failed.")).toBeInTheDocument());
  });

  it("never calls the old /collect endpoint when Mobile Money Push is selected", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { collection_id: "id", payment_status: "pending", message: "Pending." },
      }),
    });

    render(<PaymentForm slug="test-slug" link={link} />);
    selectWalletPush();
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    fireEvent.click(screen.getByRole("button", { name: /Pay/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("/collect");
  });

  it("polls the collection-status endpoint and shows cancelled/rejected copy distinctly from a generic failure", async () => {
    vi.useFakeTimers();
    try {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            data: { collection_id: "col-1", payment_status: "pending", message: "Payment request sent to your phone. Please approve using your PIN." },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, data: { status: "user_cancelled", message: "You cancelled this payment." } }),
        });

      render(<PaymentForm slug="test-slug" link={link} />);
      selectWalletPush();
      fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
      fireEvent.click(screen.getByRole("button", { name: /Pay/ }));

      // Wait for the awaiting_confirmation render (proves the polling
      // effect has already scheduled its setTimeout) before advancing
      // fake timers — advancing too early races the effect itself.
      await vi.waitFor(() =>
        expect(
          screen.getByText("Payment request sent to your phone. Please approve using your PIN."),
        ).toBeInTheDocument(),
      );
      await vi.advanceTimersByTimeAsync(3000);
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

      const [pollUrl] = fetchMock.mock.calls[1];
      expect(String(pollUrl)).toContain("/public/payment-links/test-slug/collections/col-1/status");

      await vi.waitFor(() => expect(screen.getByText("Payment cancelled")).toBeInTheDocument());
      expect(screen.getByText("You cancelled this payment.")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
