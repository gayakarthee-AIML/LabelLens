import { TopBar } from "@/components/TopBar";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/context/I18nContext";
import { LANGUAGE_LABELS, type SupportedLanguage } from "@/i18n/locales";
import { ROLE_LABELS } from "@/api/auth";

export function SettingsPage() {
  const { user } = useAuth();
  const { t, language, setLanguage } = useTranslation();

  return (
    <>
      <TopBar title={t("settings.title")} />
      <div className="app-content">
        <div className="panel">
          <div className="panel-title">Account</div>
          <table className="data-table">
            <tbody>
              <tr><td>Official ID</td><td className="mono">{user?.officialId}</td></tr>
              <tr><td>Name</td><td>{user?.fullName}</td></tr>
              <tr><td>Role</td><td>{user ? ROLE_LABELS[user.role] : "—"}</td></tr>
              <tr><td>Jurisdiction</td><td>{user?.jurisdiction ?? "—"}</td></tr>
            </tbody>
          </table>
        </div>

        <div className="panel">
          <div className="panel-title">{t("settings.language")}</div>
          <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
            Changes the LabelLens interface language. This is a reference implementation of the
            i18n architecture (see <code>src/i18n/locales.ts</code>) covering navigation, login, and
            this settings screen — extending remaining screens follows the same <code>t(key)</code> pattern.
            It does not change which languages PaddleOCR reads on the backend; that is controlled
            independently via <code>PADDLEOCR_LANGS</code>.
          </p>
          <div className="field" style={{ maxWidth: 260 }}>
            <select value={language} onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}>
              {Object.entries(LANGUAGE_LABELS).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </>
  );
}
