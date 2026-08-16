"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon } from "@/components/portal/icon";

import { DOCS_NAV } from "./nav-items";

export function DocsSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();

  return (
    <>
      {open && <div onClick={onClose} className="fixed inset-0 bg-black/40 z-40 lg:hidden" aria-hidden />}
      <aside
        className={`fixed left-0 top-16 h-[calc(100%-4rem)] w-64 bg-primary border-r border-on-primary/10 overflow-y-auto z-40 transition-transform duration-200 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between px-4 py-4 lg:hidden border-b border-on-primary/10">
          <span className="text-sm font-bold text-on-primary">Documentation</span>
          <button onClick={onClose} className="text-on-primary/70 p-1" aria-label="Close menu">
            <Icon name="close" />
          </button>
        </div>
        <nav className="px-4 py-6 space-y-7">
          {DOCS_NAV.map((group) => (
            <div key={group.label}>
              <p className="text-xs font-semibold text-on-primary/50 uppercase tracking-wide px-3 mb-2.5">{group.label}</p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      className={
                        isActive
                          ? "block px-3 py-2.5 rounded-lg text-on-primary font-bold bg-on-primary/15 border-l-4 border-on-primary text-sm"
                          : "block px-3 py-2.5 rounded-lg text-on-primary/75 hover:text-on-primary hover:bg-on-primary/10 transition-colors text-sm font-medium"
                      }
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
