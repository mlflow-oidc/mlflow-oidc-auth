export type RuntimeConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

let cachedConfig: RuntimeConfig | null = null;
let inFlightPromise: Promise<RuntimeConfig> | null = null;

function fetchRuntimeConfigFallback(
  signal?: AbortSignal
): Promise<RuntimeConfig> {
  if (cachedConfig) return Promise.resolve(cachedConfig);
  if (inFlightPromise) return inFlightPromise;

  inFlightPromise = fetch("./config.json", { cache: "no-store", signal }).then(
    async (res) => {
      if (!res.ok) {
        inFlightPromise = null;
        throw new Error(`Failed to load config.json: ${res.statusText}`);
      }
      const cfg = (await res.json()) as RuntimeConfig;
      cachedConfig = cfg;
      inFlightPromise = null;
      return cfg;
    }
  );

  return inFlightPromise;
}

export function getRuntimeConfig(signal?: AbortSignal): Promise<RuntimeConfig> {
  if (cachedConfig) return Promise.resolve(cachedConfig);

  if (inFlightPromise) return inFlightPromise;

  return fetchRuntimeConfigFallback(signal);
}
