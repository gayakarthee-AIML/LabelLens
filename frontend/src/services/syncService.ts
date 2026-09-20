// Drains the offline queue whenever connectivity returns. This talks to the
// real backend through the api/ layer — there is no local fallback pathway
// once the network is back; either the sync succeeds against the server or
// it is recorded as FAILED and retried later.
import { listPendingSync, markSyncAttempt, enqueueSync } from "./offlineDb";
import { createInspection, uploadInspectionImage, runAnalysis } from "@/api/inspections";
import { isBackendUnreachable } from "@/api/client";
import type { Inspection } from "@/types";

let syncing = false;
type Listener = (status: "idle" | "syncing" | "done") => void;
const listeners = new Set<Listener>();

export function onSyncStatusChange(fn: Listener) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(status: "idle" | "syncing" | "done") {
  listeners.forEach((l) => l(status));
}

export async function trySyncPending(): Promise<void> {
  if (syncing || !navigator.onLine) return;
  syncing = true;
  notify("syncing");

  try {
    const pending = await listPendingSync();
    for (const inspection of pending) {
      await enqueueSync(inspection.id);
      try {
        await syncOne(inspection);
        await markSyncAttempt(inspection.id, true);
      } catch (err) {
        if (isBackendUnreachable(err)) {
          // Backend still unreachable — stop the batch, try again on next
          // "online" event rather than burning through every retry at once.
          await markSyncAttempt(inspection.id, false, "Backend unreachable");
          break;
        }
        await markSyncAttempt(inspection.id, false, (err as Error).message);
      }
    }
  } finally {
    syncing = false;
    notify("done");
  }
}

async function syncOne(inspection: Inspection): Promise<void> {
  // Recreate the server-side record, push each captured image, then trigger
  // the real analysis pipeline (OpenCV/YOLO/PaddleOCR/rule engine) so the
  // synced inspection ends up in the same state a live-connected inspection
  // would have reached.
  const remote = await createInspection({
    productName: inspection.productName,
    brand: inspection.brand,
    category: inspection.category,
    location: inspection.location ?? undefined
  });

  for (const image of inspection.images) {
    if (!image.uploaded) {
      await uploadInspectionImage(remote.id, image);
    }
  }

  await runAnalysis(remote.id);
}

export function registerConnectivityListeners() {
  window.addEventListener("online", () => {
    void trySyncPending();
  });
}
