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
 *
 * A request that *hangs* has to reach that same fallback, which is what the timeout is for. The
 * login button is gated on `loading`, so a proxy that accepts `/providers` and then holds the
 * connection open would otherwise leave the only sign-in control disabled forever — every
 * failure mode here has to end in a page someone can log in from.
 */
const FETCH_TIMEOUT_MS = 5000;

export function useProviders(basePath: string): ProvidersState {
  const [providers, setProviders] = useState<IdentityProvider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    fetchProviders(basePath, controller.signal)
      .then((found) => {
        if (active) setProviders(found);
      })
      .catch(() => {
        if (active) setProviders([]);
      })
      .finally(() => {
        clearTimeout(timeout);
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [basePath]);

  return { providers, loading };
}
