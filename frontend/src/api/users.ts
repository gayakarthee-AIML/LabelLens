import { request } from "./client";
import type { UserRecord, UserRole } from "@/types";

// Administrator-only — enforced server-side by require_permission("MANAGE_USERS").
export async function listUsers(): Promise<UserRecord[]> {
  return request<UserRecord[]>("/users");
}

export interface CreateUserPayload {
  officialId: string;
  fullName: string;
  role: UserRole;
  password: string;
  jurisdiction?: string;
}

export async function createUser(payload: CreateUserPayload): Promise<UserRecord> {
  return request<UserRecord>("/users", { method: "POST", body: payload });
}

export interface UpdateUserPayload {
  fullName?: string;
  role?: UserRole;
  jurisdiction?: string;
  isActive?: boolean;
  password?: string;
}

export async function updateUser(userId: string, payload: UpdateUserPayload): Promise<UserRecord> {
  return request<UserRecord>(`/users/${userId}`, { method: "PATCH", body: payload });
}
