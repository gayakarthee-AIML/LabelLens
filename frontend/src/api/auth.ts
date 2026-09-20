import { request, setTokens, clearTokens } from "./client";
import type { AuthTokens, AuthUser, LoginPayload, UserRole } from "@/types";

// POST /api/v1/auth/login
// Backend contract: role in the payload is a UX hint for which login form
// was shown. The server looks up the account by officialId, verifies the
// password, and returns the ACTUAL role + permission set from the database —
// it never trusts the client-selected role. See backend/app/api/routers/auth.py.
export async function login(payload: LoginPayload): Promise<{ user: AuthUser; tokens: AuthTokens }> {
  const data = await request<{ user: AuthUser; tokens: AuthTokens }>("/auth/login", {
    method: "POST",
    body: payload,
    skipAuth: true
  });
  setTokens(data.tokens.accessToken, data.tokens.refreshToken);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await request("/auth/logout", { method: "POST" });
  } finally {
    clearTokens();
  }
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export const ROLE_LABELS: Record<UserRole, string> = {
  INSPECTOR: "Inspector",
  SENIOR_INSPECTOR: "Senior Inspector",
  ADMINISTRATOR: "Administrator",
  REGULATOR: "Regulator / Authorized Official"
};
