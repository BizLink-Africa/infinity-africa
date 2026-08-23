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

describe("PaymentForm — wallet push (temporary, hosted checkout blocked)", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the merchant, amount, and description", () => {
    render(<PaymentForm slug="test-slug" link={link} />);

    expect(screen.getByText("Paying Test Merchant")).toBeInTheDocument();
    expect(screen.getByText("TZS 25,000.00")).toBeInTheDocument();
    expect(screen.getByText("Invoice for services")).toBeInTheDocument();
  });

  it("requires a phone number when the link has none on file", () => {
    render(<PaymentForm slug="test-slug" link={link} />);

    expect(screen.getByLabelText("Phone number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay now" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    expect(screen.getByRole("button", { name: "Pay now" })).not.toBeDisabled();
  });

  it("does not ask for a phone number when the link already has one on file", () => {
    render(<PaymentForm slug="test-slug" link={{ ...link, customer_phone: "255747730270" }} />);

    expect(screen.queryByLabelText("Phone number")).not.toBeInTheDocument();
    expect(screen.getByText("For 255747730270")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay now" })).not.toBeDisabled();
  });

  it("submits to /pay/wallet-push with the phone number and shows the backend's pending message", async () => {
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
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747 730 270" } });
    fireEvent.click(screen.getByRole("button", { name: "Pay now" }));

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
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    fireEvent.click(screen.getByRole("button", { name: "Pay now" }));

    await waitFor(() => expect(screen.getByText("This payment attempt failed.")).toBeInTheDocument());
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
      fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
      fireEvent.click(screen.getByRole("button", { name: "Pay now" }));

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

  it("shows a success state once the poll reports completed", async () => {
    vi.useFakeTimers();
    try {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            data: { collection_id: "col-2", payment_status: "pending", message: "Payment request sent to your phone. Please approve using your PIN." },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, data: { status: "completed", message: "Payment completed successfully." } }),
        });

      render(<PaymentForm slug="test-slug" link={link} />);
      fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
      fireEvent.click(screen.getByRole("button", { name: "Pay now" }));

      await vi.waitFor(() =>
        expect(
          screen.getByText("Payment request sent to your phone. Please approve using your PIN."),
        ).toBeInTheDocument(),
      );
      await vi.advanceTimersByTimeAsync(3000);

      await vi.waitFor(() => expect(screen.getByText("Payment successful")).toBeInTheDocument());
    } finally {
      vi.useRealTimers();
    }
  });
});
