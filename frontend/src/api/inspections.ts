import { request } from "./client";
import type { CapturedImage, EvidenceBundle, Inspection, ReportHistoryEntry } from "@/types";

export interface CreateInspectionPayload {
  productName: string;
  brand: string;
  category: string;
  location?: string;
}

export async function createInspection(payload: CreateInspectionPayload): Promise<Inspection> {
  return request<Inspection>("/inspections", { method: "POST", body: payload });
}

export async function uploadInspectionImage(
  inspectionId: string,
  image: CapturedImage
): Promise<{ remoteImageId: string; qualityFlags: string[] }> {
  // The captured dataURL is converted to a Blob and sent as multipart/form-data
  // so the backend's OpenCV/YOLO/PaddleOCR pipeline (see
  // backend/app/services/cv_service.py, ocr_service.py) can run on the raw bytes.
  const blob = await (await fetch(image.dataUrl)).blob();
  const form = new FormData();
  form.append("slot", image.slot);
  form.append("capturedAt", image.capturedAt);
  form.append("file", blob, `${image.slot}.jpg`);

  return request(`/inspections/${inspectionId}/images`, {
    method: "POST",
    body: form,
    isFormData: true
  });
}

export async function runAnalysis(inspectionId: string): Promise<Inspection> {
  // Triggers, server-side: preprocessing -> YOLO region detection -> PaddleOCR
  // -> declaration extraction -> font/readability analysis -> barcode
  // cross-check -> rule engine evaluation. Returns the fully populated
  // inspection record.
  return request<Inspection>(`/inspections/${inspectionId}/analyze`, { method: "POST" });
}

export async function analyzeEcommerceListing(inspectionId: string, url: string): Promise<Inspection> {
  // Server-side pipeline: fetch listing -> HTML/JSON-LD/text extraction ->
  // product image download -> existing PaddleOCR pipeline on those images ->
  // multimodal AI extraction for anything still missing -> the SAME
  // unmodified rule engine used for physical inspections. See
  // backend/app/api/routers/inspections.py's ecommerce analyze endpoint.
  return request<Inspection>(`/inspections/${inspectionId}/ecommerce/analyze`, {
    method: "POST",
    body: { url }
  });
}

export async function submitHumanVerification(
  inspectionId: string,
  updates: {
    declarationOverrides?: { declarationType: string; detectedText: string; status: string }[];
    ruleOverrides?: { ruleId: string; status: string; note: string }[];
    notes?: string;
    productName?: string;
    brand?: string;
  }
): Promise<Inspection> {
  return request<Inspection>(`/inspections/${inspectionId}/verify`, {
    method: "POST",
    body: updates
  });
}

export async function finalizeInspection(inspectionId: string): Promise<Inspection> {
  return request<Inspection>(`/inspections/${inspectionId}/finalize`, { method: "POST" });
}

export async function getInspection(inspectionId: string): Promise<Inspection> {
  return request<Inspection>(`/inspections/${inspectionId}`);
}

export interface SearchInspectionsParams {
  query?: string;
  status?: string;
  category?: string;
  inspectorId?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export async function searchInspections(
  params: SearchInspectionsParams
): Promise<{ items: Inspection[]; total: number }> {
  const qs = new URLSearchParams(
    Object.entries(params).reduce((acc, [k, v]) => {
      if (v !== undefined && v !== "") acc[k] = String(v);
      return acc;
    }, {} as Record<string, string>)
  );
  return request(`/inspections?${qs.toString()}`);
}

export async function downloadPdfReport(inspectionId: string): Promise<Blob> {
  // Backend renders this with ReportLab (backend/app/services/pdf_service.py).
  return request<Blob>(`/inspections/${inspectionId}/report.pdf`, { method: "GET" });
}

export async function downloadEditableReport(inspectionId: string): Promise<Blob> {
  // Backend renders this with python-docx (backend/app/services/docx_service.py).
  return request<Blob>(`/inspections/${inspectionId}/report.docx`, { method: "GET" });
}

export async function getEvidence(inspectionId: string): Promise<EvidenceBundle> {
  return request<EvidenceBundle>(`/inspections/${inspectionId}/evidence`);
}

export async function addEvidenceNote(
  inspectionId: string,
  imageId: string,
  note: string
): Promise<{ remoteImageId: string; note: string }> {
  return request(`/inspections/${inspectionId}/images/${imageId}/note`, {
    method: "POST",
    body: { note }
  });
}

export async function reverifyBarcode(
  inspectionId: string
): Promise<{ rawValue: string | null; symbology: string | null; registryMatch: string; note: string }> {
  return request(`/inspections/${inspectionId}/barcode/verify`, { method: "POST" });
}

export async function listRecentReports(limit = 25): Promise<ReportHistoryEntry[]> {
  return request<ReportHistoryEntry[]>(`/inspections/reports/recent?limit=${limit}`);
}
