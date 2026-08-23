import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WebhooksPage from "./page";

describe("WebhooksPage", () => {
  it("lists the reversal-protection event names", () => {
    render(<WebhooksPage />);

    expect(screen.getByText("collection.pending_review")).toBeInTheDocument();
    expect(screen.getAllByText("collection.reversed").length).toBeGreaterThan(0);
    expect(screen.getByText("payment_link.payment_reversed")).toBeInTheDocument();
  });

  it("renders the full status lifecycle table", () => {
    render(<WebhooksPage />);

    for (const status of ["created", "processing", "pending_clearance", "successful", "failed", "cancelled", "reversed"]) {
      expect(screen.getAllByText(status).length).toBeGreaterThan(0);
    }
  });

  it("shows both Python and Node.js signature verification examples", () => {
    render(<WebhooksPage />);

    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("javascript — Node.js")).toBeInTheDocument();
    expect(screen.getAllByText(/timingSafeEqual|compare_digest/).length).toBe(2);
  });

  it("warns not to mark an order paid before collection.successful", () => {
    render(<WebhooksPage />);

    expect(screen.getByText(/Mark an order paid only on collection\.successful/)).toBeInTheDocument();
  });
});
