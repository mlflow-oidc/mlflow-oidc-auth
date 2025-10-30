import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./app.tsx";
import { LoadingSpinner } from "./shared/components/loading-spinner.tsx";
import { initializeTheme } from "./shared/utils/theme-utils.ts";
import { getRuntimeConfig } from "./shared/services/runtime-config";

async function init() {
  initializeTheme();

  const config = await getRuntimeConfig();

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
