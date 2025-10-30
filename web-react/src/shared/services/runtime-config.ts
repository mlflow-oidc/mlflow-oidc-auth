export type RuntimeConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

let cachedConfig: RuntimeConfig | null = null;
let inFlightPromise: Promise<RuntimeConfig> | null = null;

export function getRuntimeConfig(signal?: AbortSignal): Promise<RuntimeConfig> {
  if (cachedConfig) return Promise.resolve(cachedConfig);
  if (inFlightPromise) return inFlightPromise;

  inFlightPromise = fetch("./config.json", { cache: "no-store", signal })
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
