import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/merchant/overview",
}));

describe("Sidebar", () => {
  it("does not show an Upgrade Plan CTA", async () => {
    const { Sidebar } = await import("./sidebar");
    const { container } = render(<Sidebar open onClose={() => {}} />);

    expect(screen.queryByText(/Upgrade Plan/i)).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Upgrade Plan/i);
  });

  it("shows a Team nav item linking to /merchant/users", async () => {
    const { Sidebar } = await import("./sidebar");
    render(<Sidebar open onClose={() => {}} />);

    expect(screen.getByRole("link", { name: /Team/i })).toHaveAttribute("href", "/merchant/users");
  });
});
