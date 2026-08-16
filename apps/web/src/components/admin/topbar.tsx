"use client";

import { useState } from "react";

import { Icon } from "@/components/portal/icon";
import { logout } from "@/lib/supabase/logout";

export function AdminTopbar({
  onOpenSidebar,
  notificationCount = 0,
}: {
  onOpenSidebar: () => void;
  notificationCount?: number;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

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
        <div className="flex-1 max-w-xl hidden sm:flex items-center bg-surface-container-low rounded-full px-4 py-2 border border-outline-variant focus-within:border-primary transition-colors">
          <Icon name="search" className="text-on-surface-variant mr-2 text-[20px]" />
          <input
            className="bg-transparent border-none outline-none w-full text-sm text-on-surface focus:ring-0 placeholder:text-on-surface-variant p-0"
            placeholder="Search merchants, transactions, invoices, payment links..."
            type="text"
          />
        </div>
      </div>
      <div className="flex items-center gap-1 md:gap-3">
        <button className="text-on-surface-variant hover:bg-surface-container-high transition-colors p-2 rounded-full relative" aria-label="Notifications">
          <Icon name="notifications" />
          {notificationCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full border-2 border-surface" />
          )}
        </button>
        <button className="text-on-surface-variant hover:bg-surface-container-high transition-colors p-2 rounded-full hidden sm:block">
          <Icon name="help_outline" />
        </button>
        <div className="relative flex items-center gap-2 pl-2 md:pl-4 md:border-l border-outline-variant">
          <button
            onClick={() => setMenuOpen((open) => !open)}
            className="flex items-center gap-2"
            aria-label="Account menu"
          >
            <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-sm border border-outline-variant shrink-0">
              A
            </div>
            <span className="text-sm font-medium text-on-surface hidden lg:block">Admin User</span>
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
