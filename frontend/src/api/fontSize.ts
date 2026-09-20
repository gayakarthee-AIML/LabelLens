import { request } from "./client";
import type { FontSizeCheckResult, FontSizeStandard } from "@/types";

// The reference-card font-size check needs the raw image bytes (not a
// data URL) so the backend can run real contour detection + OCR on it —
// same multipart pattern as uploadInspectionImage in api/inspections.ts.
export async function checkFontSize(
  dataUrl: string,
  options?: { cardWidthMm?: number; cardHeightMm?: number; inspectionId?: string }
): Promise<FontSizeCheckResult> {
  const blob = await (await fetch(dataUrl)).blob();
  const form = new FormData();
  form.append("file", blob, "font-size-check.jpg");
  if (options?.cardWidthMm) form.append("cardWidthMm", String(options.cardWidthMm));
  if (options?.cardHeightMm) form.append("cardHeightMm", String(options.cardHeightMm));
  if (options?.inspectionId) form.append("inspectionId", options.inspectionId);

  return request<FontSizeCheckResult>("/font-size/check", {
    method: "POST",
    body: form,
    isFormData: true
  });
}

export async function listFontSizeStandards(): Promise<FontSizeStandard[]> {
  return request<FontSizeStandard[]>("/font-size/standards");
}

export async function updateFontSizeStandard(
  standardId: string,
  patch: Partial<Pick<FontSizeStandard, "name" | "keyword" | "minHeightMm" | "source" | "enabled">>
): Promise<FontSizeStandard> {
  return request<FontSizeStandard>(`/font-size/standards/${standardId}`, {
    method: "PATCH",
    body: patch
  });
}
