import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import OnboardingRequirementsPage from "./page";

describe("OnboardingRequirementsPage", () => {
  it("mentions the required onboarding documents", () => {
    render(<OnboardingRequirementsPage />);

    expect(screen.getAllByText(/NIDA/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/TIN certificate/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Business licence/).length).toBeGreaterThan(0);
  });
});
