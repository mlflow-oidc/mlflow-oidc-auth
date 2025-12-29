import { Button } from "../button";

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
      <div className="flex flex-wrap h-full justify-center content-center items-center gap-4 text-status-danger dark:text-status-danger-dark p-8">
        <p className="text-xl font-medium">{`Error: ${error.message}`}</p>
        {onRetry && (
          <Button variant="danger" onClick={onRetry}>
            Try Again
          </Button>
        )}
      </div>
    );
  }

  return null;
}
