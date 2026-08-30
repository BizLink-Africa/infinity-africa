import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AdminNotificationSettingsRow } from "@/lib/admin/types";

const updateAdminMerchantNotificationSettingsAction = vi.fn();

vi.mock("@/lib/admin/live-actions", () => ({
  updateAdminMerchantNotificationSettingsAction: (...args: unknown[]) =>
    updateAdminMerchantNotificationSettingsAction(...args),
}));

const settings: AdminNotificationSettingsRow = {
  id: "settings-1",
  merchant_id: "merchant-1",
  merchant_name: "Masanja Traders",
  merchant_code: "27048391",
  primary_notification_email: "owner@example.com",
  secondary_notification_email: "finance@example.com",
  collection_notifications_enabled: true,
  last_notification_sent_at: "2026-08-30T10:00:00Z",
  last_notification_status: "sent",
  failed_notification_count: 0,
  recent_deliveries: [
    {
      id: "delivery-1",
      recipient_email: "owner@example.com",
      status: "sent",
      provider_message_id: "resend-1",
      error_message: null,
      related_resource_id: "collection-1",
      created_at: "2026-08-30T10:00:00Z",
    },
  ],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-30T10:00:00Z",
  updated_by: null,
};

describe("Super Admin NotificationSettingsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows primary/secondary emails, status, and delivery history", async () => {
    const { NotificationSettingsCard } = await import("./notification-settings-card");
    render(<NotificationSettingsCard merchantId="merchant-1" settings={settings} />);

    expect(screen.getAllByText("owner@example.com").length).toBeGreaterThan(0);
    expect(screen.getByText("finance@example.com")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText(/sent ·/)).toBeInTheDocument();
  });

  it("shows failed delivery count when deliveries have failed", async () => {
    const { NotificationSettingsCard } = await import("./notification-settings-card");
    render(
      <NotificationSettingsCard
        merchantId="merchant-1"
        settings={{ ...settings, failed_notification_count: 3, last_notification_status: "failed" }}
      />,
    );

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("submits the edit form with the current field values", async () => {
    updateAdminMerchantNotificationSettingsAction.mockResolvedValue({ error: null });
    const { NotificationSettingsCard } = await import("./notification-settings-card");
    render(<NotificationSettingsCard merchantId="merchant-1" settings={settings} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(updateAdminMerchantNotificationSettingsAction).toHaveBeenCalledTimes(1));
    const formData = updateAdminMerchantNotificationSettingsAction.mock.calls[0][2] as FormData;
    expect(formData.get("primary_notification_email")).toBe("owner@example.com");
    expect(formData.get("secondary_notification_email")).toBe("finance@example.com");
  });

  it("surfaces a failed save's error message", async () => {
    updateAdminMerchantNotificationSettingsAction.mockResolvedValue({
      error: "Duplicate notification emails are not allowed.",
    });
    const { NotificationSettingsCard } = await import("./notification-settings-card");
    render(<NotificationSettingsCard merchantId="merchant-1" settings={settings} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(screen.getByText("Duplicate notification emails are not allowed.")).toBeInTheDocument(),
    );
  });
});
