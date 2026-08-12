import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useAuthErrors } from "./hooks/use-auth-errors";
import { Button } from "../../shared/components/button";
import {
  faHeart,
  faExclamationCircle,
} from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import DarkModeToggle from "../../shared/components/dark-mode-toggle";
import { useProviders } from "./hooks/use-providers";
import { withNextTarget } from "./services/provider-service";
import { ProviderPicker } from "./components/provider-picker";

export const AuthPage = () => {
  const config = useRuntimeConfig();

  const errors = useAuthErrors();
  const hasErrors = errors.length > 0;

  // Carried through to whichever provider is chosen. Not validated here: the server does that
  // (`_sanitize_next`), and a second implementation would be a second thing to keep correct.
  const nextTarget = new URLSearchParams(window.location.search).get("next");

  const { providers, loading } = useProviders(config.basePath);

  // One provider is the shape almost every deployment has, and it must look exactly as it did
  // before this page learned about several: one button, the configured label, no chrome. That
  // also covers a server too old to serve /providers, which reports none.
  const singleProvider = providers.length <= 1;
  const loginHref = withNextTarget(
    providers.length === 1
      ? providers[0].login_url
      : `${config.basePath}/login`,
    nextTarget,
  );
  // Same fallback chain the picker uses: a provider configured without a label still gets a
  // button with words on it rather than an empty one.
  const buttonText =
    providers.length === 1
      ? providers[0].display_name || providers[0].id
      : config.provider;

  const currentYear = new Date().getFullYear();

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-between
    bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark"
    >
      <div className="absolute top-4 right-4">
        <DarkModeToggle />
      </div>
      <div className="flex-1 flex  items-center justify-center w-full">
        <div
          className="w-full max-w-2xs p-8 rounded-md shadow flex flex-col items-center
           bg-ui-bg text-ui-text
           dark:bg-ui-bg-dark dark:text-ui-text-dark"
        >
          <div className="flex items-center gap-2 mb-6">
            <img src="favicon.svg" alt="Logo" className="w-10 h-10" />
            <h1 className="text-2xl font-semibold">MLflow</h1>
          </div>

          {hasErrors && (
            <div
              role="alert"
              className="mb-6 w-full flex items-start p-4 rounded border
                         bg-red-100 dark:bg-red-900 border-red-200 dark:border-red-800
                         text-red-800 dark:text-red-100"
            >
              <div className="shrink-0 mr-3 mt-0.5">
                <FontAwesomeIcon
                  icon={faExclamationCircle}
                  className="h-4 w-4"
                />
              </div>
              <div className="flex-1 text-sm font-medium">
                <ul className="list-disc list-inside space-y-1">
                  {errors.map((error) => (
                    <li key={error} className="wrap-break-word">
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {loading ? (
            // Deliberately not a live link. The fallback button says "sign in with <the default
            // provider>", and until the list arrives that may not be the provider this user
            // belongs to — a click landing in the 300ms before it does would start a login
            // against the wrong IdP, and with provisioning on, create an account there.
            <Button
              variant="primary"
              className="w-full py-2 text-base"
              disabled
              aria-busy="true"
              data-testid="providers-loading"
            >
              {buttonText}
            </Button>
          ) : singleProvider ? (
            <a href={loginHref} className="w-full">
              <Button variant="primary" className="w-full py-2 text-base">
                {buttonText}
              </Button>
            </a>
          ) : (
            <ProviderPicker providers={providers} next={nextTarget} />
          )}
        </div>
      </div>

      <footer className="w-full py-6 px-6 md:px-10 text-sm text-ui-text/60 dark:text-ui-text-dark/40">
        <div className="mx-auto w-full max-w-5xl flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <a
            href="https://kharkevich.com/"
            target="_blank"
            rel="noopener"
            className="inline-flex items-center gap-3 hover:text-ui-text dark:hover:text-ui-text-dark transition-colors"
          >
            &copy; {currentYear} Kharkevich Engineering Lab
          </a>
          <a
            href="https://github.com/sponsors/mlflow-oidc?o=esb"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-3 hover:text-ui-text dark:hover:text-ui-text-dark transition-colors sm:justify-end"
          >
            <FontAwesomeIcon
              icon={faHeart}
              className="color-text-btn-secondary"
            />
            <span>Support the project</span>
          </a>
        </div>
      </footer>
    </div>
  );
};

export default AuthPage;
