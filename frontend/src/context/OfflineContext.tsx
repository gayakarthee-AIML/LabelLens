import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { registerConnectivityListeners, trySyncPending, onSyncStatusChange } from "@/services/syncService";
import { getSyncQueue } from "@/services/offlineDb";
import type { SyncQueueEntry } from "@/types";

interface OfflineContextValue {
  isOnline: boolean;
  syncStatus: "idle" | "syncing" | "done";
  queue: SyncQueueEntry[];
  refreshQueue: () => Promise<void>;
  forceSync: () => Promise<void>;
}

const OfflineContext = createContext<OfflineContextValue | null>(null);

export function OfflineProvider({ children }: { children: ReactNode }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "done">("idle");
  const [queue, setQueue] = useState<SyncQueueEntry[]>([]);

  const refreshQueue = async () => setQueue(await getSyncQueue());

  useEffect(() => {
    registerConnectivityListeners();
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    const unsubscribe = onSyncStatusChange((status) => {
      setSyncStatus(status);
      void refreshQueue();
    });
    void refreshQueue();
    if (navigator.onLine) void trySyncPending();
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      unsubscribe();
    };
  }, []);

  return (
    <OfflineContext.Provider
      value={{ isOnline, syncStatus, queue, refreshQueue, forceSync: trySyncPending }}
    >
      {children}
    </OfflineContext.Provider>
  );
}

export function useOffline() {
  const ctx = useContext(OfflineContext);
  if (!ctx) throw new Error("useOffline must be used inside OfflineProvider");
  return ctx;
}
