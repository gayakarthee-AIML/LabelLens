import type { RuleResult } from "@/types";
import { useTranslation } from "@/context/I18nContext";

export function RuleResultList({ results }: { results: RuleResult[] }) {
  const { t } = useTranslation();
  if (results.length === 0) {
    return <div className="empty-state">{t("rule.noResults")}</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {results.map((r) => (
        <div key={r.rule.ruleId} style={{ border: "1px solid var(--color-line)", padding: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <strong style={{ fontSize: 14 }}>
              {r.rule.ruleId} — {r.rule.name}
            </strong>
            <span className={`badge ${r.status.toLowerCase()}`}>{r.status}</span>
          </div>
          <p style={{ fontSize: 13.5, margin: "6px 0", color: "var(--color-ink-soft)" }}>{r.finding}</p>
          <div style={{ fontSize: 12, color: "var(--color-steel)" }}>
            <span>{t("rule.severity")}: {r.rule.severity}</span> · <span>{t("rule.confidence")}: {Math.round(r.confidence * 100)}%</span> ·{" "}
            <span>{t("rule.source")}: {r.rule.source} (v{r.rule.version})</span>
          </div>
          {r.status !== "PASS" && (
            <p style={{ fontSize: 12.5, marginTop: 6, fontStyle: "italic" }}>{t("rule.recommendation")}: {r.recommendation}</p>
          )}
        </div>
      ))}
    </div>
  );
}
