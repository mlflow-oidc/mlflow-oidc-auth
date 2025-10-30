import { createContext, use } from "react";
import type { RuntimeConfig } from "../services/runtime-config";

const RuntimeConfigContext = createContext<RuntimeConfig | null>(null);

export function useRuntimeConfig(): RuntimeConfig {
  const ctx = use(RuntimeConfigContext);
  if (!ctx) {
    throw new Error(
      "useRuntimeConfig must be used within RuntimeConfigProvider"
    );
  }
  return ctx;
}

export function useOptionalRuntimeConfig(): RuntimeConfig | null {
  return use(RuntimeConfigContext);
}

export { RuntimeConfigContext };
