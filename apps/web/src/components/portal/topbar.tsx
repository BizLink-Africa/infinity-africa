"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { merchantLogout } from "@/lib/supabase/logout";
import { getMyMembership, listMyNotifications } from "@/lib/portal/api";
import { MERCHANT_ROLES, USER_ROLE_LABELS } from "@/lib/portal/roles";
import type { AppNotification, MerchantUser } from "@/lib/portal/types";

import { Icon } from "./icon";
import { useRole } from "./role-context";

function initials(name: string | null, email: string | null): string {
  if (name) {
    const parts = name.split(" ").filter(Boolean);
    return parts
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  }
  return email ? email[0].toUpperCase() : "?";
}

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [profile, setProfile] = useState<MerchantUser | null>(null);
  const { role, setRole } = useRole();

  useEffect(() => {
    listMyNotifications().then(setNotifications);
    getMyMembership().then(setProfile);
  }, []);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <header className="fixed top-0 right-0 w-full md:w-[calc(100%-16rem)] z-30 bg-surface/80 backdrop-blur-md shadow-sm flex justify-between items-center h-16 px-4 md:px-8 border-b border-surface-container-highest">
      <div className="flex items-center gap-4 flex-1">
        <button
          onClick={onOpenSidebar}
          className="md:hidden text-on-surface-variant p-2 -ml-2 rounded-lg hover:bg-surface-container-highest"
          aria-label="Open menu"
        >
          <Icon name="menu" />
        </button>
        <div className="relative w-full max-w-md hidden sm:block">
          <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
          <input
            className="w-full pl-10 pr-4 py-2 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm text-on-surface placeholder-outline transition-all"
            placeholder="Search transactions, invoices, payment links..."
            type="text"
          />
        </div>
      </div>
      <div className="flex items-center gap-2 md:gap-4">
        <label className="hidden md:flex items-center gap-2 text-xs font-semibold text-on-surface-variant">
          Role
          <select
            value={role}
            onChange={(event) => setRole(event.target.value as typeof role)}
            className="bg-surface-container-low border border-surface-container-highest rounded-lg text-xs font-semibold text-on-surface px-2.5 py-1.5 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            aria-label="Switch role"
          >
            {MERCHANT_ROLES.map((option) => (
              <option key={option} value={option}>
                {USER_ROLE_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <Link
          href="/merchant/payment-links"
          className="hidden lg:flex items-center gap-2 bg-primary-container text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Icon name="add" className="text-[20px]" />
          New Payment Link
        </Link>
        <div className="relative">
          <button
            onClick={() => setNotifOpen((open) => !open)}
            className="p-2 text-on-surface-variant hover:bg-surface-container-high transition-colors rounded-full relative"
            aria-label="Notifications"
          >
            <Icon name="notifications" />
            {unreadCount > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />}
          </button>
          {notifOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} aria-hidden />
              <div className="absolute right-0 top-11 z-50 w-80 max-h-96 overflow-y-auto bg-surface border border-surface-container-highest rounded-lg shadow-ambient">
                <div className="px-4 py-3 border-b border-surface-container-highest">
                  <p className="text-sm font-semibold text-on-background">Notifications</p>
                </div>
                {notifications.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-on-surface-variant text-center">You&apos;re all caught up.</p>
                ) : (
                  <ul className="divide-y divide-surface-container-highest">
                    {notifications.slice(0, 10).map((notification) => (
                      <li key={notification.id} className={`px-4 py-3 text-sm ${!notification.is_read ? "bg-primary-container/5" : ""}`}>
                        <p className="font-medium text-on-background">{notification.title}</p>
                        <p className="text-xs text-on-surface-variant mt-0.5">{notification.body}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
        <a
          href="mailto:support@infinityafrica.net"
          className="p-2 text-on-surface-variant hover:bg-surface-container-high transition-colors rounded-full hidden sm:block"
          title="Contact support"
        >
          <Icon name="help_outline" />
        </a>
        <div className="relative ml-2">
          <button
            onClick={() => setMenuOpen((open) => !open)}
            className="w-9 h-9 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-sm border border-outline-variant shrink-0"
            aria-label="Account menu"
          >
            {initials(profile?.full_name ?? null, profile?.email ?? null)}
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} aria-hidden />
              <div className="absolute right-0 top-11 z-50 w-64 bg-surface border border-surface-container-highest rounded-lg shadow-ambient overflow-hidden">
                <div className="px-4 py-3 border-b border-surface-container-highest">
                  <p className="text-sm font-semibold text-on-background truncate">
                    {profile?.full_name ?? "Signed in"}
                  </p>
                  <p className="text-xs text-on-surface-variant truncate">{profile?.email ?? ""}</p>
                  {profile && (
                    <span className="inline-block mt-1.5 text-[11px] font-semibold bg-primary-container/10 text-primary px-2 py-0.5 rounded-full">
                      {USER_ROLE_LABELS[profile.role]}
                    </span>
                  )}
                </div>
                <Link
                  href="/merchant/profile"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2.5 text-sm text-on-surface hover:bg-surface-container-low transition-colors"
                >
                  Profile &amp; Settings
                </Link>
                <form action={merchantLogout}>
                  <button
                    type="submit"
                    className="w-full text-left px-4 py-2.5 text-sm text-on-surface hover:bg-surface-container-low transition-colors"
                  >
                    Log out
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
