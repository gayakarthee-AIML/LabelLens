import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { AuthUser, LoginPayload, UserRole } from "@/types";
import { login as apiLogin, logout as apiLogout, fetchCurrentUser } from "@/api/auth";
import { clearTokens } from "@/api/client";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<AuthUser>;
  logout: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Frontend permission table. This is a UX convenience ONLY (hide/show nav,
// disable buttons) — the backend re-checks every request against its own
// RBAC table (backend/app/core/rbac.py) and must never trust this map.
export const PERMISSIONS: Record<string, UserRole[]> = {
  CREATE_INSPECTION: ["INSPECTOR", "SENIOR_INSPECTOR"],
  APPROVE_INSPECTION: ["SENIOR_INSPECTOR"],
  MANAGE_RULES: ["ADMINISTRATOR"],
  MANAGE_USERS: ["ADMINISTRATOR"],
  VIEW_AUDIT_LOG: ["ADMINISTRATOR"],
  VIEW_ENFORCEMENT_DASHBOARD: ["SENIOR_INSPECTOR", "REGULATOR", "ADMINISTRATOR"],
  VIEW_ANALYTICS: ["SENIOR_INSPECTOR", "REGULATOR", "ADMINISTRATOR"]
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("labellens.accessToken");
    if (!token) {
      setLoading(false);
      return;
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(() => {
        clearTokens();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (payload) => {
        const { user: loggedInUser } = await apiLogin(payload);
        setUser(loggedInUser);
        return loggedInUser;
      },
      logout: async () => {
        await apiLogout();
        setUser(null);
      },
      hasRole: (...roles) => !!user && roles.includes(user.role)
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function can(role: UserRole | undefined, permission: keyof typeof PERMISSIONS): boolean {
  if (!role) return false;
  return PERMISSIONS[permission]?.includes(role) ?? false;
}
