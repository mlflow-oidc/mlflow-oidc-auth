import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./app.tsx";
import { LoadingSpinner } from "./shared/components/loading-spinner.tsx";
import { initializeTheme } from "./shared/utils/theme-utils.ts";

type AppConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

async function init() {
  initializeTheme();
  const runtimeConfigPromise = fetch("./config.json", {
    cache: "no-store",
  }).then(async (res) => {
    if (!res.ok)
      throw new Error(`Failed to load config.json: ${res.statusText}`);
    return (await res.json()) as AppConfig;
  });

  (
    globalThis as unknown as { __RUNTIME_CONFIG_PROMISE__?: Promise<AppConfig> }
  ).__RUNTIME_CONFIG_PROMISE__ = runtimeConfigPromise;

  const config = await runtimeConfigPromise;

  (
    globalThis as unknown as { __RUNTIME_CONFIG__?: AppConfig }
  ).__RUNTIME_CONFIG__ = config;

  // const basePath = config.basePath;
  const uiPath = config.uiPath;
  const provider = config.provider;

  const basename = `${uiPath}`.replace(/\/+$/, "");

  const { BrowserRouter } = await import("react-router");

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter basename={basename}>
        <Suspense fallback={<LoadingSpinner />}>
          <App btnText={provider} />
        </Suspense>
      </BrowserRouter>
    </StrictMode>
  );
}

await init();
