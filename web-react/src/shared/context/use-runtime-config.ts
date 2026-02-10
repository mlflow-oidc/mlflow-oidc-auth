import { createContext, use } from "react";
import type { RuntimeConfig } from "../services/runtime-config";

export const RuntimeConfigContext = createContext<RuntimeConfig | null>(null);

export function useRuntimeConfig(): RuntimeConfig {
  const ctx = use(RuntimeConfigContext);
  if (!ctx) {
    throw new Error(
      "useRuntimeConfig must be used within a RuntimeConfigProvider",
    );
  }
  return ctx;
}
