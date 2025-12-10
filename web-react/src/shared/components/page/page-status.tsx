export default function PageStatus({
  isLoading,
  loadingText,
  error,
  onRetry,
}: {
  isLoading: boolean;
  loadingText?: string;
  error?: Error | null;
  onRetry?: () => void;
}) {
  if (isLoading) {
    return (
      <div className="flex h-full justify-center items-center p-8">
        <p className="text-lg font-medium animate-pulse text-text-primary dark:text-text-primary-dark">
          {loadingText ?? "Loading..."}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-wrap h-full justify-center content-center items-center gap-2 text-red-600">
        <p className="text-xl">{`Error: ${error.message}`}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="ml-4 p-2 bg-red-100 rounded hover:bg-red-200 cursor-pointer"
          >
            Try Again
          </button>
        )}
      </div>
    );
  }

  return null;
}
