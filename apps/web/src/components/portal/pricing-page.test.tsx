import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("PricingPage", () => {
  it("does not show an Upgrade Plan CTA", async () => {
    const { default: PricingPage } = await import("@/app/portal/pricing/page");
    const { container } = render(<PricingPage />);

    expect(screen.queryByText(/Upgrade Plan/i)).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Upgrade Plan/i);
    // The real fee schedule stays — only the fabricated "plan" CTA is gone.
    expect(screen.getByText("Fee Schedule")).toBeInTheDocument();
  });
});
