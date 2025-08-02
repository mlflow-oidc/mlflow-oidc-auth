import { RuntimeConfig } from '../app/core/models/runtime-config.interface';

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: RuntimeConfig;
  }
}

// This export is required to make this file a module
export {};
