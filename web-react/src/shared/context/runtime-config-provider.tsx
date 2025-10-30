import React from "react";
import type { RuntimeConfig } from "../services/runtime-config";
import { RuntimeConfigContext } from "./use-runtime-config";

interface RuntimeConfigProviderProps {
  config: RuntimeConfig;
  children: React.ReactNode;
}

export const RuntimeConfigProvider = ({
  config,
  children,
}: RuntimeConfigProviderProps) => {
  return <RuntimeConfigContext value={config}>{children}</RuntimeConfigContext>;
};
