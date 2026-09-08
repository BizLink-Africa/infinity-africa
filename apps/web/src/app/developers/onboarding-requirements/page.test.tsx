import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import OnboardingRequirementsPage from "./page";

describe("OnboardingRequirementsPage", () => {
  it("lists the identity/compliance items and that they're requested during review, not uploaded", () => {
    render(<OnboardingRequirementsPage />);

    expect(screen.getAllByText(/NIDA/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/TIN certificate/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Business licence/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Requested during review/).length).toBeGreaterThan(0);
    expect(screen.getByText(/not uploaded during onboarding/i)).toBeInTheDocument();
  });
});
