import { useMemo } from "react";

export const useAuthErrors = (): string[] => {
  const errors = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);

    const rawErrors = urlParams.getAll("error");

    const sanitizedErrors = rawErrors
      .map((error) => {
        const decodedError = error.replace(/\+/g, " ");
        return decodedError.trim();
      })
      .filter((error) => error.length > 0);

    return sanitizedErrors;
  }, []);

  return errors;
};
