import { request } from "./client";
import type { AnalyticsSummary, DashboardSummary } from "@/types";

export async function fetchDashboardSummary(params?: { from?: string; to?: string }): Promise<DashboardSummary> {
  const qs = new URLSearchParams(params as Record<string, string>);
  return request<DashboardSummary>(`/dashboard/summary?${qs.toString()}`);
}

export async function fetchEnforcementOverview() {
  return request("/dashboard/enforcement");
}

export async function fetchAnalytics(): Promise<AnalyticsSummary> {
  return request<AnalyticsSummary>("/dashboard/analytics");
}
