import type { AuthPageProps } from "../../core/types/pages";
import { useAuthErrors } from "./hooks/use-auth-errors";

export const AuthPage = ({ btnText }: AuthPageProps) => {
  const errors = useAuthErrors();
  const hasErrors = errors.length > 0;

  const errorStyles = hasErrors
    ? "bg-red-50 dark:bg-red-900/50 border-red-400 text-red-700 dark:text-red-300"
    : "border-transparent text-lg dark:text-gray-400";

  return (
    <div className="min-h-screen flex items-center justify-center bg-white dark:bg-gray-900">
      <div className="w-full max-w-md p-8 rounded-md shadow bg-white dark:bg-gray-800">
        <h1 className="text-2xl font-semibold mb-6 text-gray-900 dark:text-gray-100">
          Sign in
        </h1>

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

        <a href="/login">
          <button
            type="button"
            className="w-full rounded-md text-btn-primary-text
              bg-btn-primary hover:bg-btn-primary-hover dark:bg-btn-primary-dark dark:hover:bg-btn-primary-hover-dark dark:text-btn-primary-text-dark
              px-[12px] py-[4px]
               cursor-pointer"
          >
            {btnText}
          </button>
        </a>
      </div>
    </div>
  );
};

export default AuthPage;
