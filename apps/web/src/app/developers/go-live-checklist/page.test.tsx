import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import GoLiveChecklistPage from "./page";

describe("GoLiveChecklistPage", () => {
  it("covers credentials, integration, security, and the hosted-checkout warning", () => {
    render(<GoLiveChecklistPage />);

    expect(screen.getByText("Credentials")).toBeInTheDocument();
    expect(screen.getByText("Security best practices")).toBeInTheDocument();
    expect(screen.getAllByText(/never expose|Never expose|Never ship a secret key/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Hosted Checkout is not available")).toBeInTheDocument();
  });

  it("states the order-paid rule matches the webhooks page", () => {
    render(<GoLiveChecklistPage />);

    expect(screen.getAllByText(/collection\.successful/).length).toBeGreaterThan(0);
  });
});
