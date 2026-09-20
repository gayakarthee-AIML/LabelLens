// IndexedDB-backed offline store. This is the real offline-first layer:
// inspections created without connectivity are written here first and are
// fully usable (viewable, editable, reportable-in-summary-form) before ever
// reaching the backend. It is deliberately independent of the Workbox HTTP
// cache configured in vite.config.ts — HTTP caching helps with GETs, but a
// queued write needs its own retry bookkeeping, which is what this module is for.
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { Inspection, SyncQueueEntry } from "@/types";

interface LabelLensDB extends DBSchema {
  inspections: {
    key: string;
    value: Inspection;
    indexes: { "by-synced": number; "by-status": string; "by-createdAt": string };
  };
  syncQueue: {
    key: string;
    value: SyncQueueEntry;
  };
}

let dbPromise: Promise<IDBPDatabase<LabelLensDB>> | null = null;

export function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<LabelLensDB>("labellens-offline", 1, {
      upgrade(db) {
        const inspections = db.createObjectStore("inspections", { keyPath: "id" });
        inspections.createIndex("by-synced", "syncedFlag");
        inspections.createIndex("by-status", "status");
        inspections.createIndex("by-createdAt", "createdAt");

        db.createObjectStore("syncQueue", { keyPath: "inspectionId" });
      }
    });
  }
  return dbPromise;
}

export async function saveInspectionLocally(inspection: Inspection): Promise<void> {
  const db = await getDb();
  // idb indexes need a plain value on the object; store synced as 0/1 too.
  await db.put("inspections", { ...inspection, syncedFlag: inspection.synced ? 1 : 0 } as any);
}

export async function getLocalInspection(id: string): Promise<Inspection | undefined> {
  const db = await getDb();
  return db.get("inspections", id);
}

export async function listLocalInspections(): Promise<Inspection[]> {
  const db = await getDb();
  return db.getAll("inspections");
}

export async function listPendingSync(): Promise<Inspection[]> {
  const all = await listLocalInspections();
  return all.filter((i) => !i.synced);
}

export async function enqueueSync(inspectionId: string): Promise<void> {
  const db = await getDb();
  const existing = await db.get("syncQueue", inspectionId);
  await db.put("syncQueue", {
    inspectionId,
    attempts: existing?.attempts ?? 0,
    lastAttemptAt: existing?.lastAttemptAt ?? null,
    lastError: existing?.lastError ?? null,
    status: "PENDING"
  });
}

export async function markSyncAttempt(inspectionId: string, ok: boolean, error?: string) {
  const db = await getDb();
  const existing = await db.get("syncQueue", inspectionId);
  await db.put("syncQueue", {
    inspectionId,
    attempts: (existing?.attempts ?? 0) + 1,
    lastAttemptAt: new Date().toISOString(),
    lastError: ok ? null : error ?? "Unknown error",
    status: ok ? "SYNCED" : "FAILED"
  });
  if (ok) {
    const inspection = await getLocalInspection(inspectionId);
    if (inspection) await saveInspectionLocally({ ...inspection, synced: true });
  }
}

export async function getSyncQueue(): Promise<SyncQueueEntry[]> {
  const db = await getDb();
  return db.getAll("syncQueue");
}
