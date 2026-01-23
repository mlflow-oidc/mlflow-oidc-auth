export type RuntimeConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

let cachedConfig: RuntimeConfig | null = null;
let inFlightPromise: Promise<RuntimeConfig> | null = null;

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: RuntimeConfig;
  }
}

export function getRuntimeConfig(signal?: AbortSignal): Promise<RuntimeConfig> {
  if (cachedConfig) return Promise.resolve(cachedConfig);
  if (window.__RUNTIME_CONFIG__) {
    cachedConfig = window.__RUNTIME_CONFIG__;
    return Promise.resolve(cachedConfig);
  }
  if (inFlightPromise) return inFlightPromise;

  // Fallback: In development (or if index.html script failed), try to fetch.
  // In production, the index.html script should have already loaded this.
  const configUrl = import.meta.env.DEV
    ? "/config.json"
    : new URL("../config.json", import.meta.url).toString();

  inFlightPromise = fetch(configUrl, { cache: "no-store", signal })
    .then(async (res) => {
      if (!res.ok) {
        throw new Error(
          `Failed to load config.json: ${res.status} ${res.statusText}`
        );
      }

      const cfg = (await res.json()) as RuntimeConfig;
      cachedConfig = cfg;
      return cfg;
    })
    .finally(() => {
      inFlightPromise = null;
    });

  return inFlightPromise;
}
