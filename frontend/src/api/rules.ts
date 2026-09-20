import { request } from "./client";
import type { ComplianceRule } from "@/types";

// Rule management endpoints — Administrator only (enforced server-side by RBAC,
// see backend/app/core/rbac.py). The frontend never evaluates or stores the
// authoritative rule set; it only displays what the backend rule engine used.
export async function listRules(params?: { category?: string; enabled?: boolean; query?: string }) {
  const qs = new URLSearchParams(
    Object.entries(params || {}).reduce((acc, [k, v]) => {
      if (v !== undefined) acc[k] = String(v);
      return acc;
    }, {} as Record<string, string>)
  );
  return request<ComplianceRule[]>(`/rules?${qs.toString()}`);
}

export async function createRule(rule: Omit<ComplianceRule, "version">): Promise<ComplianceRule> {
  return request<ComplianceRule>("/rules", { method: "POST", body: rule });
}

export async function updateRule(ruleId: string, patch: Partial<ComplianceRule>): Promise<ComplianceRule> {
  return request<ComplianceRule>(`/rules/${ruleId}`, { method: "PATCH", body: patch });
}

export async function toggleRule(ruleId: string, enabled: boolean): Promise<ComplianceRule> {
  return request<ComplianceRule>(`/rules/${ruleId}/toggle`, { method: "POST", body: { enabled } });
}

export async function exportRules(): Promise<Blob> {
  return request<Blob>("/rules/export", { method: "GET" });
}

export async function importRules(file: File): Promise<{ imported: number; version: string }> {
  const form = new FormData();
  form.append("file", file);
  return request("/rules/import", { method: "POST", body: form, isFormData: true });
}

export async function ruleUpdateHistory() {
  return request<{ version: string; publishedAt: string; source: string; changeSummary: string }[]>(
    "/rules/history"
  );
}
