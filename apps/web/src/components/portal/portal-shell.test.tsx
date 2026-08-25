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
  it("caps content width at 1280px and centers it by default, for the same left-aligned layout every other page uses", async () => {
    const { PortalShell } = await import("./portal-shell");
    const { container } = render(<PortalShell>content</PortalShell>);

    const main = container.querySelector("main");
    expect(main?.className).toContain("max-w-[1280px]");
    expect(main?.className).toContain("mx-auto");
    expect(main?.className).toContain("md:ml-64");
  });

  it("removes both the width cap AND mx-auto when fullWidth is set, without changing the left offset/top spacing", async () => {
    // No mx-auto here at all — not even alongside max-w-none — since an
    // auto margin paired with a fixed md:ml-64 margin on the same side is
    // exactly the kind of conflict whose winner depends on utility-class
    // build order rather than anything visible in this file; removing the
    // class outright removes the ambiguity, not just one symptom of it.
    const { PortalShell } = await import("./portal-shell");
    const { container } = render(<PortalShell fullWidth>content</PortalShell>);

    const main = container.querySelector("main");
    expect(main?.className).not.toContain("max-w-[1280px]");
    expect(main?.className).not.toContain("mx-auto");
    expect(main?.className).toContain("md:ml-64");
    expect(main?.className).toContain("pt-20");
  });
});
