import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => currentSearchParams,
}));

vi.mock("@/lib/portal/api", () => ({
  listApiKeys: vi.fn().mockResolvedValue([]),
  getMyMerchant: vi.fn().mockResolvedValue({ status: "active", kyc_status: "verified", api_access_suspended: false }),
  createApiKey: vi.fn(),
  renameApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
  rotateApiKey: vi.fn(),
  updateApiKeyIpWhitelist: vi.fn(),
  getWebhookConfig: vi.fn().mockResolvedValue({ webhook_url: null, subscribed_events: null, has_secret: false, last_delivery: null }),
  listWebhookEvents: vi.fn().mockResolvedValue([]),
  updateWebhookConfig: vi.fn(),
  sendTestWebhook: vi.fn(),
  listIpAllowlist: vi.fn().mockResolvedValue([]),
  createIpAllowlistEntry: vi.fn(),
  deleteIpAllowlistEntry: vi.fn(),
  listApiLogs: vi.fn().mockResolvedValue([]),
}));

describe("ApiCredentialsTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearchParams = new URLSearchParams();
  });

  it("renders a tab for each of the six sections", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    for (const label of ["Overview", "API Keys", "Webhooks", "IP Allowlist", "API Logs", "Developer Docs"]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });

  it("defaults to the Overview tab and shows the quick setup checklist", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    expect(await screen.findByText("Quick Setup Checklist")).toBeInTheDocument();
  });

  it("switches to the API Keys tab and renders the real API Keys content", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(screen.getByRole("tab", { name: /API Keys/ }));
    expect(await screen.findByText(/Use secret keys only on your backend/)).toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/portal/api-credentials?tab=keys", { scroll: false });
  });

  it("switches to the Webhooks tab and renders webhook configuration", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(screen.getByRole("tab", { name: /Webhooks/ }));
    expect(await screen.findByText("Webhook Configuration")).toBeInTheDocument();
  });

  it("switches to the IP Allowlist tab and renders the IP form", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(screen.getByRole("tab", { name: /IP Allowlist/ }));
    expect(await screen.findByText("Add a Server IP")).toBeInTheDocument();
  });

  it("switches to the API Logs tab and renders the logs table", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(screen.getByRole("tab", { name: /API Logs/ }));
    expect(await screen.findByText(/No API requests yet/)).toBeInTheDocument();
  });

  it("switches to the Developer Docs tab and renders the docs grid", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(screen.getByRole("tab", { name: /Developer Docs/ }));
    expect(await screen.findByText("REST API Overview")).toBeInTheDocument();
  });

  it("reads the initial tab from the ?tab= URL query parameter", async () => {
    currentSearchParams = new URLSearchParams("tab=webhooks");
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    expect(await screen.findByText("Webhook Configuration")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Webhooks/ })).toHaveAttribute("aria-selected", "true");
  });

  it("ignores an invalid ?tab= value and falls back to Overview", async () => {
    currentSearchParams = new URLSearchParams("tab=not-a-real-tab");
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    expect(await screen.findByText("Quick Setup Checklist")).toBeInTheDocument();
  });

  it("clicking a checklist item on Overview navigates to that tab", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    fireEvent.click(await screen.findByText("Create API key"));
    await waitFor(() => expect(screen.getByRole("tab", { name: /API Keys/ })).toHaveAttribute("aria-selected", "true"));
  });

  it("the tab bar scrolls horizontally instead of wrapping the layout on narrow (mobile) viewports", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    expect(screen.getByRole("tab", { name: /Overview/ }).closest(".overflow-x-auto")).toBeInTheDocument();
  });

  it("disables the horizontal scroll container from lg upward, so no scrollbar shows on desktop/laptop", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const tabList = screen.getByRole("tablist");
    expect(tabList.className).toContain("overflow-x-auto");
    expect(tabList.className).toContain("lg:overflow-visible");
  });

  it("all six tabs sit in a single non-wrapping row on mobile so none of them (like Developer Docs) get pushed off-screen", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const tabList = screen.getByRole("tablist");
    expect(tabList.className).toContain("flex-nowrap");
    expect(screen.getByRole("tab", { name: /Developer Docs/ })).toBeInTheDocument();
  });

  it("switches the tab list to a vertical column from lg upward, sized to its own 240px grid track", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    const { container } = render(<ApiCredentialsTabs />);

    const tabList = screen.getByRole("tablist");
    expect(tabList.className).toContain("lg:flex-col");

    const grid = container.querySelector(".grid");
    expect(grid?.className).toContain("lg:grid-cols-[240px_1fr]");
    expect(grid?.contains(tabList)).toBe(true);
  });

  it("stacks the menu above the content in a single column by default (mobile), only splitting into two columns from lg", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    const { container } = render(<ApiCredentialsTabs />);

    const grid = container.querySelector(".grid");
    expect(grid?.className).toContain("grid-cols-1");
  });

  it("gives the active tab the Infinity green background and white text, on both the horizontal and vertical layouts", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const overviewTab = screen.getByRole("tab", { name: /Overview/ });
    expect(overviewTab.className).toContain("bg-primary-container");
    expect(overviewTab.className).toContain("text-on-primary");

    fireEvent.click(screen.getByRole("tab", { name: /Webhooks/ }));
    const webhooksTab = await screen.findByRole("tab", { name: /Webhooks/ });
    expect(webhooksTab.className).toContain("bg-primary-container");
    expect(overviewTab.className).not.toContain("bg-primary-container");
  });

  it("gives inactive vertical tabs a visible border instead of the active fill", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const inactiveTab = screen.getByRole("tab", { name: /API Keys/ });
    expect(inactiveTab.className).toContain("lg:border-surface-container-highest");
  });

  it("lets the content column shrink instead of forcing the page wider (guards against a wide table causing page-level horizontal scroll)", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    expect(screen.getByRole("tabpanel").className).toContain("min-w-0");
  });
});
