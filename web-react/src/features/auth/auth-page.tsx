import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useAuthErrors } from "./hooks/use-auth-errors";
import { Button } from "../../shared/components/button";
import { faHeart, faExclamationCircle } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

export const AuthPage = () => {
  const config = useRuntimeConfig();

  const buttonText = config.provider;
  const loginHref = `${config.basePath}/login`;

  const errors = useAuthErrors();
  const hasErrors = errors.length > 0;

  const currentYear = new Date().getFullYear();

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-between
    bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark"
    >
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
                <FontAwesomeIcon icon={faExclamationCircle} className="h-4 w-4" />
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

          <a href={loginHref} className="w-full">
            <Button variant="primary" className="w-full py-2 text-base">
              {buttonText}
            </Button>
          </a>
        </div>
      </div>

      <footer className="w-full py-6 flex flex-col ml-10 items-start gap-4 text-sm text-ui-text/60 dark:text-ui-text-dark/40">
        <div className="flex gap-4">
          <span>
            &copy; {currentYear} mlflow-oidc-auth
          </span>
          <a
            href="https://github.com/sponsors/mlflow-oidc?o=esb"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-4 hover:text-ui-text dark:hover:text-ui-text-dark transition-colors"
          >
            <FontAwesomeIcon icon={faHeart} className="color-text-btn-secondary" />
            <span>Support the project</span>
          </a>
        </div>
      </footer>
    </div>
  );
};

export default AuthPage;
