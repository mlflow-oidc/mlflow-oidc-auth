import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./app.tsx";
import { LoadingSpinner } from "./shared/components/loading-spinner.tsx";

type AppConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

async function init() {
  const res = await fetch("./config.json", { cache: "no-store" });

  if (!res.ok) {
    throw new Error(`Failed to load config.json: ${res.statusText}`);
  }

  const config = (await res.json()) as AppConfig;

  const basePath = config.basePath;
  const uiPath = config.uiPath;
  const provider = config.provider;

  const basename = `${basePath}${uiPath}`.replace(/\/+$/, "");

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
