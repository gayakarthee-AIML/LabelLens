import { request } from "./client";

export interface ProductRecord {
  barcode: string;
  name: string;
  brand: string;
  manufacturer: string;
  declaredNetQuantity: string;
  category: string;
  inspectionCount: number;
  violationCount: number;
}

export async function lookupBarcode(barcode: string): Promise<ProductRecord | null> {
  // Backend checks the local product registry and (where configured) a
  // pluggable adapter for an official manufacturer/government database.
  // See backend/app/services/barcode_service.py — REGISTRY_ADAPTER.
  try {
    return await request<ProductRecord>(`/products/${encodeURIComponent(barcode)}`);
  } catch (err: any) {
    if (err?.status === 404) return null;
    throw err;
  }
}

export async function getProductHistory(barcode: string) {
  return request(`/products/${encodeURIComponent(barcode)}/history`);
}
