import { useMemo } from "react";
import DOMPurify from "dompurify";

export const useAuthErrors = (): string[] => {
  const errors = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);

    const rawErrors = urlParams.getAll("error");

    const sanitizedErrors = rawErrors
      .map((error) => {
        const decodedError = error.replace(/\+/g, " ");

        const purifiedError = DOMPurify.sanitize(decodedError, {
          ALLOWED_TAGS: [],
          ALLOWED_ATTR: [],
        });
        return purifiedError.trim();
      })
      .filter((error) => error.length > 0);

    return sanitizedErrors;
  }, []);

  return errors;
};
