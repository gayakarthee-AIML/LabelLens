import { NavLink } from "react-router-dom";
import { useAuth, can } from "@/context/AuthContext";
import { useTranslation } from "@/context/I18nContext";
import { ROLE_LABELS } from "@/api/auth";

export function Sidebar() {
  const { user } = useAuth();
  const { t } = useTranslation();
  if (!user) return null;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="mark">{t("app.name")}</div>
        <div className="sub">{t("app.tagline")}</div>
      </div>
      <nav>
        <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : "")}>
          {t("nav.dashboard")}
        </NavLink>
        {can(user.role, "CREATE_INSPECTION") && (
          <NavLink to="/inspections/new" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.newInspection")}
          </NavLink>
        )}
        {can(user.role, "CREATE_INSPECTION") && (
          <NavLink to="/font-size-check" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.fontSizeCheck")}
          </NavLink>
        )}
        <NavLink to="/search" className={({ isActive }) => (isActive ? "active" : "")}>
          {t("nav.search")}
        </NavLink>
        <NavLink to="/reports" className={({ isActive }) => (isActive ? "active" : "")}>
          {t("nav.reports")}
        </NavLink>
        {can(user.role, "VIEW_ENFORCEMENT_DASHBOARD") && (
          <NavLink to="/enforcement" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.enforcement")}
          </NavLink>
        )}
        {can(user.role, "VIEW_ANALYTICS") && (
          <NavLink to="/analytics" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.analytics")}
          </NavLink>
        )}
        {can(user.role, "MANAGE_RULES") && (
          <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.rules")}
          </NavLink>
        )}
        {can(user.role, "MANAGE_USERS") && (
          <NavLink to="/users" className={({ isActive }) => (isActive ? "active" : "")}>
            {t("nav.users")}
          </NavLink>
        )}
        <NavLink to="/offline-queue" className={({ isActive }) => (isActive ? "active" : "")}>
          {t("nav.offlineQueue")}
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
          {t("nav.settings")}
        </NavLink>
      </nav>
      <div className="sidebar-footer">
        {ROLE_LABELS[user.role]}
        <br />
        {user.officialId}
      </div>
    </aside>
  );
}
