import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
});
