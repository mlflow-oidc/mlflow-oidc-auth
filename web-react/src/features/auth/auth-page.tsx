import type { AuthPageProps } from "../../core/types/pages";

export const AuthPage = ({ btnText }: AuthPageProps) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white dark:bg-gray-900">
      <div className="w-full max-w-md p-8 rounded-md shadow bg-white dark:bg-gray-800">
        <h1 className="text-2xl font-semibold mb-6 text-gray-900 dark:text-gray-100">
          Sign in
        </h1>

        {/* Error placeholder */}
        <div
          role="status"
          aria-live="polite"
          className="mb-4 rounded-md border border-transparent p-3 text-lg dark:text-gray-400"
        >
          Future error messages will render here
        </div>

        <a href="/login">
          <button
            type="button"
            className="w-full rounded-md text-white
              bg-[rgb(34,114,180)] hover:bg-[rgb(14,83,139)] active:brightness-90
              px-[12px] py-[4px]
              focus:outline-none focus:ring-2 focus:ring-blue-400
              dark:hover:brightness-95 dark:active:brightness-90 cursor-pointer"
          >
            {btnText}
          </button>
        </a>
      </div>
    </div>
  );
};

export default AuthPage;
