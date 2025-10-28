import React from "react";

export const LoadingSpinner: React.FC = () => {
  return (
    <div className="flex justify-center items-center w-full h-screen min-h-64">
      <div className="flex flex-col items-center">
        <div
          className=" w-12 h-12 border-4 border-ui-secondary-bg dark:border-ui-secondary-bg-dark border-t-btn-primary dark:border-t-btn-primary-dark rounded-full animate-fast-spin"
          role="status"
          aria-label="Loading"
        ></div>

        <div className="mt-4 text-text-secondary text-lg font-sans">
          Loading...
        </div>
      </div>
    </div>
  );
};
