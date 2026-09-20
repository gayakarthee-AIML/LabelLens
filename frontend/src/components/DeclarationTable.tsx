import type { Declaration } from "@/types";
import { useTranslation } from "@/context/I18nContext";

const LABELS: Record<string, string> = {
  COMMON_NAME: "Common / Generic Name",
  NET_QUANTITY: "Net Quantity",
  MRP: "Maximum Retail Price",
  MANUFACTURER_DETAILS: "Manufacturer / Packer / Importer",
  COUNTRY_OF_ORIGIN: "Country of Origin",
  MFG_DATE: "Month/Year of Manufacture or Packing",
  CONSUMER_CARE: "Consumer Care Details",
  UNIT_SALE_PRICE: "Unit Sale Price"
};

function statusBadgeClass(status: Declaration["status"]): string {
  switch (status) {
    case "PRESENT":
      return "present";
    case "MISSING":
      return "missing";
    case "AMBIGUOUS":
    case "REVIEW":
      return "review";
    default:
      return "missing";
  }
}

export function DeclarationTable({ declarations }: { declarations: Declaration[] }) {
  const { t } = useTranslation();

  if (declarations.length === 0) {
    return <div className="empty-state">{t("declaration.table.empty")}</div>;
  }

  const sourceLabel = (source: string) => {
    if (source === "webpage") return t("declaration.source.webpage");
    if (source === "ai_extraction") return t("declaration.source.aiExtraction");
    return source;
  };

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>{t("declaration.table.header.declaration")}</th>
          <th>{t("declaration.table.header.detectedText")}</th>
          <th>{t("declaration.table.header.source")}</th>
          <th>{t("declaration.table.header.confidence")}</th>
          <th>{t("declaration.table.header.textHeight")}</th>
          <th>{t("declaration.table.header.readability")}</th>
          <th>{t("declaration.table.header.status")}</th>
        </tr>
      </thead>
      <tbody>
        {declarations.map((d) => (
          <tr key={d.declarationType}>
            <td>{LABELS[d.declarationType] ?? d.declarationType}</td>
            <td className="mono">{d.detectedText ?? t("declaration.table.notDetected")}</td>
            <td>
              {sourceLabel(d.sourceImage)}
              {d.sourceImage === "ai_extraction" && d.aiRationale && (
                <span title={d.aiRationale} style={{ marginLeft: 4, cursor: "help" }}>
                  ⓘ
                </span>
              )}
            </td>
            <td className="mono">{Math.round(d.confidence * 100)}%</td>
            <td className="mono">
              {d.estimatedTextHeightPx
                ? `${d.estimatedTextHeightPx.toFixed(1)} px (estimated — physical measurement requires calibrated reference)`
                : "—"}
            </td>
            <td>{d.readability ?? "—"}</td>
            <td>
              <span className={`badge ${statusBadgeClass(d.status)}`}>
                {d.sourceImage === "ai_extraction" ? "AI Extracted — Needs Verification" : d.status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

