import type { InspectionStatus } from "@/types";
import { useTranslation } from "@/context/I18nContext";
import type { TranslationKey } from "@/i18n/locales";

const LABEL_KEYS: Record<InspectionStatus, TranslationKey> = {
  COMPLIANT: "status.compliant",
  NON_COMPLIANT: "status.nonCompliant",
  REVIEW_REQUIRED: "status.reviewRequired",
  DRAFT: "status.draft"
};

export function ComplianceStamp({ status }: { status: InspectionStatus }) {
  const { t } = useTranslation();
  return <span className={`stamp ${status.toLowerCase()}`}>{t(LABEL_KEYS[status])}</span>;
}
