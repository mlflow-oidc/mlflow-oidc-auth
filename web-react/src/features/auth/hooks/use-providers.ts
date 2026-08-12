import { useEffect, useState } from "react";

import {
  fetchProviders,
  type IdentityProvider,
} from "../services/provider-service";

export type ProvidersState = {
  providers: IdentityProvider[];
  loading: boolean;
};

/**
 * The identity providers the login page may offer (issue #317).
 *
 * Starts as loading with an empty list. A failure — an older server with no `/providers`, a
 * network blip — resolves to an empty list rather than an error state: the page then renders the
 * single-provider login it has always had, which is a working page rather than a dead end.
 */
export function useProviders(basePath: string): ProvidersState {
  const [providers, setProviders] = useState<IdentityProvider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    fetchProviders(basePath, controller.signal)
      .then((found) => {
        if (active) setProviders(found);
      })
      .catch(() => {
        if (active) setProviders([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [basePath]);

  return { providers, loading };
}
