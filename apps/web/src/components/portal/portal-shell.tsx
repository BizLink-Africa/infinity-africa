"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { isPathAllowedForRole, USER_ROLE_LABELS } from "@/lib/portal/roles";

import { EmptyState } from "./empty-state";
import { RoleProvider, useRole } from "./role-context";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

function RoleGuard({ children }: { children: React.ReactNode }) {
  const { role } = useRole();
  const pathname = usePathname();
  const router = useRouter();

  if (!isPathAllowedForRole(role, pathname)) {
    return (
      <EmptyState
        icon="lock"
        heading="Access restricted"
        body={`Your role (${USER_ROLE_LABELS[role]}) doesn't have access to this page. Switch roles from the topbar or head back to Overview.`}
        actionLabel="Go to Overview"
        onAction={() => router.push("/merchant/overview")}
      />
    );
  }

  return <>{children}</>;
}

export function PortalShell({ children, banner }: { children: React.ReactNode; banner?: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <RoleProvider>
      <div className="portal-shell-scope min-h-screen bg-background text-on-background">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <Topbar onOpenSidebar={() => setSidebarOpen(true)} />
        <main className="pt-20 md:pt-24 pb-16 px-4 md:px-8 md:ml-64 max-w-[1280px] mx-auto space-y-8">
          {banner}
          <RoleGuard>{children}</RoleGuard>
        </main>
      </div>
    </RoleProvider>
  );
}
