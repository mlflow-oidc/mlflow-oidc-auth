export const AuthPage = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center p-6 bg-white dark:bg-gray-800 rounded shadow">
        <h1 className="text-2xl font-semibold mb-6">Sign in</h1>
        <a href="/login">
          <button
            type="button"
            className="px-6 py-3 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Sign in with Demo OIDC Provider
          </button>
        </a>
      </div>
    </div>
  );
};

export default AuthPage;
