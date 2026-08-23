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
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(window, "location", { writable: true, value: { href: "" } });
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

  it("shows secure hosted-checkout copy and no payment method options", () => {
    render(<PaymentForm slug="test-slug" link={link} />);

    expect(
      screen.getByText("Secure Selcom hosted checkout. You'll choose your payment method on the checkout page."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Push USSD")).not.toBeInTheDocument();
    expect(screen.queryByText("STK Push")).not.toBeInTheDocument();
    expect(screen.queryByText("Push to Selcom Pesa")).not.toBeInTheDocument();
    expect(screen.queryByText("Dynamic QR Code")).not.toBeInTheDocument();
    expect(screen.queryByText("Pay with Mobile Money Push")).not.toBeInTheDocument();
    expect(screen.queryByText("Choose how to pay")).not.toBeInTheDocument();
  });

  it("shows a phone field and disables submit until filled when the link has no phone on file", () => {
    render(<PaymentForm slug="test-slug" link={link} />);

    expect(screen.getByLabelText("Phone number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay securely" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    expect(screen.getByRole("button", { name: "Pay securely" })).not.toBeDisabled();
  });

  it("does not show a phone field when the link already has a customer phone", () => {
    render(<PaymentForm slug="test-slug" link={{ ...link, customer_phone: "255747730270" }} />);

    expect(screen.queryByLabelText("Phone number")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay securely" })).not.toBeDisabled();
  });

  it("submits to /pay/checkout and redirects the browser to the decoded payment_gateway_url", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { collection_id: "col-1", payment_gateway_url: "https://tza.selcom.online/paymentgw/checkout/abc" },
      }),
    });

    render(<PaymentForm slug="test-slug" link={{ ...link, customer_phone: "255747730270" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Pay securely" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/public/payment-links/test-slug/pay/checkout");
    expect(init.headers["Idempotency-Key"]).toBeTruthy();

    await waitFor(() => expect(window.location.href).toBe("https://tza.selcom.online/paymentgw/checkout/abc"));
  });

  it("sends the entered phone number when the link has none on file", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { collection_id: "col-1", payment_gateway_url: "https://tza.selcom.online/paymentgw/checkout/abc" },
      }),
    });

    render(<PaymentForm slug="test-slug" link={link} />);
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "0747730270" } });
    fireEvent.click(screen.getByRole("button", { name: "Pay securely" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ customer_phone: "0747730270" });
  });

  it("shows an error with a retry button when the backend rejects the request", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ success: false, error: { message: "This payment link cannot be paid" } }),
    });

    render(<PaymentForm slug="test-slug" link={{ ...link, customer_phone: "255747730270" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Pay securely" }));

    expect(await screen.findByText("This payment link cannot be paid")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
