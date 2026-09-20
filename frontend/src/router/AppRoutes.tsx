import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Sidebar } from "@/components/Sidebar";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NewInspectionPage } from "@/pages/NewInspectionPage";
import { FontSizeCheckPage } from "@/pages/FontSizeCheckPage";
import { InspectionDetailPage } from "@/pages/InspectionDetailPage";
import { EvidenceViewerPage } from "@/pages/EvidenceViewerPage";
import { SearchPage } from "@/pages/SearchPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { RuleManagementPage } from "@/pages/RuleManagementPage";
import { EnforcementPage } from "@/pages/EnforcementPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { UserManagementPage } from "@/pages/UserManagementPage";
import { OfflineQueuePage } from "@/pages/OfflineQueuePage";
import { SettingsPage } from "@/pages/SettingsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { useAuth } from "@/context/AuthContext";

function AppShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <>{children}</>;
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">{children}</div>
    </div>
  );
}

export function AppRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inspections/new"
          element={
            <ProtectedRoute roles={["INSPECTOR", "SENIOR_INSPECTOR"]}>
              <NewInspectionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/font-size-check"
          element={
            <ProtectedRoute roles={["INSPECTOR", "SENIOR_INSPECTOR"]}>
              <FontSizeCheckPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inspections/:id"
          element={
            <ProtectedRoute>
              <InspectionDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inspections/:id/evidence"
          element={
            <ProtectedRoute>
              <EvidenceViewerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/search"
          element={
            <ProtectedRoute>
              <SearchPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rules"
          element={
            <ProtectedRoute roles={["ADMINISTRATOR"]}>
              <RuleManagementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/enforcement"
          element={
            <ProtectedRoute roles={["SENIOR_INSPECTOR", "REGULATOR", "ADMINISTRATOR"]}>
              <EnforcementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute roles={["SENIOR_INSPECTOR", "REGULATOR", "ADMINISTRATOR"]}>
              <AnalyticsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute roles={["ADMINISTRATOR"]}>
              <UserManagementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/offline-queue"
          element={
            <ProtectedRoute>
              <OfflineQueuePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  );
}
