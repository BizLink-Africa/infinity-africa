import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CollectionsApiPage from "./page";

describe("CollectionsApiPage", () => {
  it("documents all three active payment flows and their endpoints", () => {
    render(<CollectionsApiPage />);

    expect(screen.getAllByText(/Infinity Payment Page/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Selcom Pesa/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Scan QR \/ TanQR/).length).toBeGreaterThan(0);

    expect(screen.getByText("/v1/collections")).toBeInTheDocument();
    expect(screen.getByText("/v1/collections/wallet-push")).toBeInTheDocument();
    expect(screen.getByText("/v1/collections/selcom-pesa")).toBeInTheDocument();
    expect(screen.getByText("/v1/collections/qr")).toBeInTheDocument();
    expect(screen.getByText("/v1/collections/{collection_id}")).toBeInTheDocument();
    expect(screen.getByText("/v1/collections/{collection_id}/refresh-status")).toBeInTheDocument();
  });

  it("warns that a processing/pending response is not final payment success", () => {
    render(<CollectionsApiPage />);

    expect(screen.getByText(/means the prompt was sent/)).toBeInTheDocument();
  });

  it("states Infinity never generates its own QR payload", () => {
    render(<CollectionsApiPage />);

    expect(screen.getByText(/Infinity never generates its own payment QR/)).toBeInTheDocument();
  });
});
