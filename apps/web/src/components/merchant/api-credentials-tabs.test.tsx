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

  it("disables the scroll container at desktop/laptop widths so no scrollbar shows there", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const tabBar = screen.getByRole("tab", { name: /Overview/ }).closest(".overflow-x-auto");
    expect(tabBar?.className).toContain("md:overflow-visible");
  });

  it("all six tabs sit in a single non-wrapping row so none of them (like Developer Docs) get pushed off-screen", async () => {
    const { ApiCredentialsTabs } = await import("./api-credentials-tabs");
    render(<ApiCredentialsTabs />);

    const tabBar = screen.getByRole("tab", { name: /Overview/ }).closest(".overflow-x-auto");
    expect(tabBar?.className).toContain("flex-nowrap");
    expect(screen.getByRole("tab", { name: /Developer Docs/ })).toBeInTheDocument();
  });
});
