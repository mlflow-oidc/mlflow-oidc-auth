import { useCallback, useSyncExternalStore } from "react";
import type { PageSize } from "../../shared/types/table";

export const PAGE_SIZE_STORAGE_KEY = "mlflow-oidc-auth:page-size";
export const DEFAULT_PAGE_SIZE: PageSize = 20;
export const PAGE_SIZE_OPTIONS: readonly PageSize[] = [20, 40, 80, "all"];

/**
 * Parse a stored or selected value into a supported page size.
 *
 * @returns The page size, or `null` for anything that is not one of the options.
 */
export function parsePageSize(raw: unknown): PageSize | null {
  if (raw === "all") return "all";
  const value = typeof raw === "number" ? raw : Number(raw);
  return PAGE_SIZE_OPTIONS.find((option) => option === value) ?? null;
}

// One module-level store so every mounted table shares a single preference:
// changing it in one footer re-renders all subscribers.
let current: PageSize | undefined;
const listeners = new Set<() => void>();

function readStored(): PageSize {
  try {
    return (
      parsePageSize(window.localStorage.getItem(PAGE_SIZE_STORAGE_KEY)) ??
      DEFAULT_PAGE_SIZE
    );
  } catch {
    // Private mode or blocked storage: fall back to the default.
    return DEFAULT_PAGE_SIZE;
  }
}

function getSnapshot(): PageSize {
  if (current === undefined) current = readStored();
  return current;
}

function notify() {
  listeners.forEach((listener) => listener());
}

function handleStorage(event: StorageEvent) {
  if (event.key !== PAGE_SIZE_STORAGE_KEY) return;
  current = parsePageSize(event.newValue) ?? DEFAULT_PAGE_SIZE;
  notify();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) window.addEventListener("storage", handleStorage);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.removeEventListener("storage", handleStorage);
    }
  };
}

function writePageSize(size: PageSize) {
  current = size;
  try {
    window.localStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(size));
  } catch {
    // Not persisted, but still applied for this session.
  }
  notify();
}

/** Forget the in-memory value so the next read goes back to storage. Tests only. */
export function _resetPageSizeForTests(): void {
  current = undefined;
}

/**
 * The global rows-per-page preference shared by every list table, persisted
 * in `localStorage`. Reads and writes never throw: when storage is unavailable
 * the preference falls back to {@link DEFAULT_PAGE_SIZE} and lives in memory.
 */
export function usePageSize() {
  const pageSize = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const setPageSize = useCallback((size: PageSize) => {
    const parsed = parsePageSize(size);
    if (parsed !== null) writePageSize(parsed);
  }, []);
  return { pageSize, setPageSize };
}
