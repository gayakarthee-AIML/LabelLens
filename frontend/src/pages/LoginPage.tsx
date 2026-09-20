import { useState } from "react";
import type { RoleDescriptor, UserRole } from "@/types";
import { RoleCard } from "@/components/RoleCard";
import { RoleLoginForm } from "./RoleLoginForm";
import { useTranslation } from "@/context/I18nContext";
import { LANGUAGE_LABELS, type SupportedLanguage } from "@/i18n/locales";

const ROLES: RoleDescriptor[] = [
  {
    id: "INSPECTOR",
    label: "Inspector",
    tagline: "Field Inspection",
    description: "Capture, scan, and file inspections in the field, online or offline."
  },
  {
    id: "SENIOR_INSPECTOR",
    label: "Senior Inspector",
    tagline: "Review & Supervision",
    description: "Verify AI findings, approve or reject inspections, monitor enforcement."
  },
  {
    id: "ADMINISTRATOR",
    label: "Administrator",
    tagline: "System & Rules",
    description: "Manage users, compliance rules, rule versions, and integrations."
  },
  {
    id: "REGULATOR",
    label: "Regulator / Authorized Official",
    tagline: "Monitoring",
    description: "Monitor compliance, enforcement activity, and inspection statistics."
  }
];

export function LoginPage() {
  const [selectedRole, setSelectedRole] = useState<UserRole | null>(null);
  const { t, language, setLanguage } = useTranslation();

  if (selectedRole) {
    return <RoleLoginForm role={selectedRole} onBack={() => setSelectedRole(null)} />;
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-header">
          <h1>{t("app.name")}</h1>
          <p>
            {t("app.tagline")} — {t("login.selectAccessType")}
          </p>
        </div>
        <div className="role-grid">
          {ROLES.map((role) => (
            <RoleCard key={role.id} role={role} onSelect={() => setSelectedRole(role.id)} />
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "center", marginTop: 20 }}>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
            style={{ fontSize: 12.5, padding: "4px 8px", border: "1px solid var(--color-line)" }}
            aria-label={t("settings.language")}
          >
            {Object.entries(LANGUAGE_LABELS).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <p style={{ fontSize: 11.5, color: "var(--color-steel)", marginTop: 12, textAlign: "center" }}>
          Role selection determines which login form is shown. Your permissions are
          verified by the server against your authenticated account, not by this choice.
        </p>
      </div>
    </div>
  );
}
