import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PaymentMethodLogos } from "./payment-method-logos";

describe("PaymentMethodLogos", () => {
  it("renders every supported operator logo from local static assets, never a hotlinked image", () => {
    render(<PaymentMethodLogos />);

    const expectedAlts = ["M-Pesa", "Airtel Money", "Mixx by Yas", "HaloPesa", "Selcom Pesa", "TanQR / TIPS"];
    for (const alt of expectedAlts) {
      const img = screen.getByAltText(alt);
      expect(img).toBeInTheDocument();
      expect(img.getAttribute("src")).toMatch(/^\/assets\/payment-logos\//);
    }
  });
});
