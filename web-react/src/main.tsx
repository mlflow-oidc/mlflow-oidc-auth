import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./index.css";
import App from "./app.tsx";
import { LoadingSpinner } from "./shared/components/loading-spinner.tsx";
import { initializeTheme } from "./shared/utils/theme-utils.ts";
import { getRuntimeConfig } from "./shared/services/runtime-config";
import { removeTrailingSlashes } from "./shared/utils/string-utils";
import { RuntimeConfigProvider } from "./shared/context/runtime-config-provider.tsx";
import { UserProvider } from "./core/context/user-provider.tsx";
import { ToastProvider } from "./shared/components/toast/toast-context.tsx";

async function init() {
  initializeTheme();

  const config = await getRuntimeConfig();

  const basename = removeTrailingSlashes(config.uiPath);

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter basename={basename}>
        <Suspense fallback={<LoadingSpinner />}>
          <RuntimeConfigProvider config={config}>
            <UserProvider>
              <ToastProvider>
                <App />
              </ToastProvider>
            </UserProvider>
          </RuntimeConfigProvider>
        </Suspense>
      </BrowserRouter>
    </StrictMode>,
  );
}

await init();
