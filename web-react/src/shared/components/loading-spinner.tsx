import React from "react";

export const LoadingSpinner: React.FC = () => {
  return (
    <div className="flex justify-center items-center w-full h-screen min-h-64">
      <div className="flex flex-col items-center">
        <div
          className=" w-12 h-12 border-4 border-gray-200 border-t-[rgb(34,114,180)] rounded-full animate-fast-spin"
          role="status"
          aria-label="Loading"
        ></div>

        <div className="mt-4 text-gray-600 text-lg font-sans">Loading...</div>
      </div>
    </div>
  );
};
