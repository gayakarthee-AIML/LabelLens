import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import type { UserRole } from "@/types";

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading } = useAuth();

  if (loading) return <div className="empty-state">Checking session…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) {
    // Frontend gate for navigation/UX only. The corresponding API calls are
    // independently rejected by backend RBAC even if this check is bypassed.
    return (
      <div className="app-content">
        <div className="empty-state">
          Your role ({user.role.replace("_", " ")}) does not have access to this section.
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
