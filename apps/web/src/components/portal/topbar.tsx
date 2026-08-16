"use client";

import { useEffect, useState } from "react";

import { logout } from "@/lib/supabase/logout";
import { listMyNotifications } from "@/lib/portal/api";
import { MERCHANT_ROLES, USER_ROLE_LABELS } from "@/lib/portal/roles";

import { Icon } from "./icon";
import { useRole } from "./role-context";

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const { role, setRole } = useRole();

  useEffect(() => {
    listMyNotifications().then((notifications) => setUnreadCount(notifications.filter((n) => !n.is_read).length));
  }, []);

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
        <button className="hidden lg:flex items-center gap-2 bg-primary-container text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity">
          <Icon name="add" className="text-[20px]" />
          New Transaction
        </button>
        <button className="p-2 text-on-surface-variant hover:bg-surface-container-high transition-colors rounded-full relative" aria-label="Notifications">
          <Icon name="notifications" />
          {unreadCount > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />}
        </button>
        <button className="p-2 text-on-surface-variant hover:bg-surface-container-high transition-colors rounded-full hidden sm:block">
          <Icon name="help_outline" />
        </button>
        <div className="relative ml-2">
          <button
            onClick={() => setMenuOpen((open) => !open)}
            className="w-9 h-9 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-sm border border-outline-variant shrink-0"
            aria-label="Account menu"
          >
            S
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} aria-hidden />
              <div className="absolute right-0 top-11 z-50 w-40 bg-surface border border-surface-container-highest rounded-lg shadow-ambient overflow-hidden">
                <form action={logout}>
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
