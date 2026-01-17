import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useAuthErrors } from "./hooks/use-auth-errors";

export const AuthPage = () => {
  const config = useRuntimeConfig();

  const buttonText = config.provider;
  const loginHref = `${config.basePath}/login`;

  const errors = useAuthErrors();
  const hasErrors = errors.length > 0;

  const errorStyles = hasErrors
    ? "bg-red-50 dark:bg-red-900/50 border-red-400 text-red-700 dark:text-red-300"
    : "border-transparent text-lg dark:text-gray-400";

  return (
    <div
      className="min-h-screen flex items-center justify-center
    bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark"
    >
      <div
        className="w-full max-w-md p-8 rounded-md shadow
         bg-ui-bg text-ui-text
         dark:bg-ui-bg-dark dark:text-ui-text-dark"
      >
        <h1 className="text-2xl font-semibold mb-6">Sign in</h1>

        <div
          role="status"
          aria-live="polite"
          className={`mb-4 rounded-md border p-3 text-sm ${errorStyles}`}
        >
          {hasErrors ? (
            <ul className="list-disc list-inside space-y-1">
              {errors.map((error) => (
                <li key={error} className="break-words">
                  {error}
                </li>
              ))}
            </ul>
          ) : (
            "Use the button below to sign in."
          )}
        </div>

        <a href={loginHref}>
          <button
            type="button"
            className="w-full rounded-md px-[12px] py-[4px] cursor-pointer
            text-btn-primary-text bg-btn-primary hover:bg-btn-primary-hover
            dark:text-btn-primary-text-dark dark:bg-btn-primary-dark dark:hover:bg-btn-primary-hover-dark"
          >
            {buttonText}
          </button>
        </a>
      </div>
    </div>
  );
};

export default AuthPage;
