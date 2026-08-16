"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { UserRole } from "@/lib/portal/roles";

const STORAGE_KEY = "infinity_portal_role";
const DEFAULT_ROLE = UserRole.MERCHANT_ADMIN;

interface RoleContextValue {
  role: UserRole;
  setRole: (role: UserRole) => void;
}

const RoleContext = createContext<RoleContextValue>({
  role: DEFAULT_ROLE,
  setRole: () => {},
});

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<UserRole>(DEFAULT_ROLE);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && Object.values(UserRole).includes(stored as UserRole)) {
      // Deliberately a post-mount sync, not a derivable-from-props value: the
      // stored role is only knowable client-side (SSR has no localStorage),
      // so a lazy useState initializer would desync from the server-rendered
      // default and produce a hydration mismatch in role-gated UI below.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRoleState(stored as UserRole);
    }
  }, []);

  const setRole = (next: UserRole) => {
    setRoleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return <RoleContext.Provider value={{ role, setRole }}>{children}</RoleContext.Provider>;
}

export function useRole() {
  return useContext(RoleContext);
}
