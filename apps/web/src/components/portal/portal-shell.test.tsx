import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/portal/api-credentials",
  useRouter: () => ({ push: vi.fn() }),
}));

// Sidebar/Topbar pull in session/notification data-fetching (and a
// server-only-marked module transitively) that isn't relevant to what
// this file actually tests — PortalShell's own width/spacing classes on
// <main> — so they're stubbed out rather than mocking their entire
// dependency tree.
vi.mock("./sidebar", () => ({ Sidebar: () => null }));
vi.mock("./topbar", () => ({ Topbar: () => null }));

describe("PortalShell", () => {
  it("caps content width at 1280px by default, for the same left-aligned layout every other page uses", async () => {
    const { PortalShell } = await import("./portal-shell");
    const { container } = render(<PortalShell>content</PortalShell>);

    const main = container.querySelector("main");
    expect(main?.className).toContain("max-w-[1280px]");
    expect(main?.className).not.toContain("max-w-none");
    expect(main?.className).toContain("md:ml-64");
  });

  it("removes the width cap when fullWidth is set, without changing the left offset/top spacing", async () => {
    const { PortalShell } = await import("./portal-shell");
    const { container } = render(<PortalShell fullWidth>content</PortalShell>);

    const main = container.querySelector("main");
    expect(main?.className).toContain("max-w-none");
    expect(main?.className).not.toContain("max-w-[1280px]");
    expect(main?.className).toContain("md:ml-64");
    expect(main?.className).toContain("pt-20");
  });
});
