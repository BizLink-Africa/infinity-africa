"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { ToggleSwitch } from "@/components/portal/toggle-switch";
import { listTeamMembers } from "@/lib/portal/api";
import type { TeamMember } from "@/lib/portal/types";

const TABS = [
  { label: "Business Profile", href: "#profile" },
  { label: "Security", href: "#security" },
  { label: "Notifications", href: "#notifications" },
  { label: "Team Members", href: "#team" },
];

const NOTIFICATION_DEFAULTS = [
  { key: "email", title: "Email notifications", description: "Get notified by email for every transaction", checked: true },
  { key: "sms", title: "SMS alerts", description: "Receive SMS for payments over TZS 100,000", checked: true },
  { key: "link_paid", title: "Payment link paid alerts", description: "Instant alert when a customer pays via a link", checked: true },
  { key: "low_balance", title: "Low balance alerts", description: "Warn me when available balance drops below TZS 500,000", checked: false },
];

export default function SettingsPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [twoFactor, setTwoFactor] = useState(true);
  const [notifications, setNotifications] = useState(() =>
    Object.fromEntries(NOTIFICATION_DEFAULTS.map((item) => [item.key, item.checked])),
  );

  useEffect(() => {
    listTeamMembers().then(setMembers);
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader title="Settings" description="Manage your business profile, security, and team." />

      <div className="flex flex-wrap gap-2">
        {TABS.map((tab, index) => (
          <a
            key={tab.href}
            href={tab.href}
            className={
              index === 0
                ? "px-4 py-2 rounded-full bg-primary-container text-on-primary text-sm font-semibold"
                : "px-4 py-2 rounded-full bg-surface-container-low text-on-surface-variant text-sm font-semibold hover:bg-surface-container-highest transition-colors"
            }
          >
            {tab.label}
          </a>
        ))}
      </div>

      <Card id="profile" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Business Profile</h3>
        <form
          onSubmit={(event) => event.preventDefault()}
          className="grid sm:grid-cols-2 gap-5"
        >
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Business Name</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="Amani Demo Store" type="text" />
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Registered Email</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="sarah@merchant.co.tz" type="email" />
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Phone Number</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="+255 754 000 000" type="tel" />
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Business Address</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="Mbezi - Ubungo, Dar es Salaam" type="text" />
          </div>
          <button className="sm:col-span-2 w-full sm:w-auto bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity" type="submit">
            Save Changes
          </button>
        </form>
      </Card>

      <Card id="security" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Security</h3>
        <form onSubmit={(event) => event.preventDefault()} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Current Password</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Enter current password" type="password" />
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">New Password</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Enter new password" type="password" />
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Confirm New Password</label>
            <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Re-enter new password" type="password" />
          </div>
          <button className="bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity" type="submit">
            Update Password
          </button>
        </form>
        <div className="flex items-center justify-between border-t border-surface-container-highest mt-6 pt-6">
          <div>
            <p className="font-semibold text-sm text-on-background">Two-Factor Authentication</p>
            <p className="text-sm text-on-surface-variant">Add an extra layer of security to your account</p>
          </div>
          <ToggleSwitch checked={twoFactor} onChange={setTwoFactor} label="Two-factor authentication" />
        </div>
      </Card>

      <Card id="notifications" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Notifications</h3>
        <div className="divide-y divide-surface-container-highest">
          {NOTIFICATION_DEFAULTS.map((item) => (
            <div key={item.key} className="flex items-center justify-between py-3.5 first:pt-0 last:pb-0">
              <div>
                <p className="font-semibold text-sm text-on-background">{item.title}</p>
                <p className="text-sm text-on-surface-variant">{item.description}</p>
              </div>
              <ToggleSwitch
                checked={notifications[item.key]}
                onChange={(checked) => setNotifications((prev) => ({ ...prev, [item.key]: checked }))}
                label={item.title}
              />
            </div>
          ))}
        </div>
      </Card>

      <Card id="team" className="scroll-mt-24">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-2xl font-semibold text-on-background">Team Members</h3>
          <button className="bg-primary-container text-on-primary text-sm font-medium py-2 px-4 rounded-lg hover:opacity-90 transition-opacity">
            Invite Member
          </button>
        </div>
        <div className="divide-y divide-surface-container-highest">
          {members.map((member) => (
            <div key={member.id} className="flex items-center justify-between py-3.5 first:pt-0 last:pb-0">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                  {member.name
                    .split(" ")
                    .map((part) => part[0])
                    .join("")}
                </div>
                <div>
                  <p className="font-medium text-sm text-on-background">{member.name}</p>
                  <p className="text-xs text-on-surface-variant">{member.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="hidden sm:inline text-sm text-on-surface-variant">{member.role}</span>
                {member.status === "active" ? (
                  <StatusBadge label="Active" tone="positive" />
                ) : (
                  <StatusBadge label="Pending Invite" tone="neutral" />
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
