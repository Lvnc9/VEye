"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { hasCapability, type Capability, type User } from "@/lib/types";

interface CurrentUserState {
  user: User | null;
  loading: boolean;
  can: (capability: Capability) => boolean;
}

const CurrentUserContext = createContext<CurrentUserState>({
  user: null,
  loading: true,
  can: () => false,
});

/**
 * Fetches /auth/me/ once for the authenticated app shell so every page can
 * read the current user's سمت and capabilities without refetching.
 *
 * Capability checks here are for UI affordance only — hiding a button the
 * API would reject. The backend remains the enforcement point.
 */
export function CurrentUserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiGet<User>("/auth/me/")
      .then((res) => {
        if (!cancelled) setUser(res);
      })
      .catch(() => {
        // proxy.ts already guards these routes; a failure here just means we
        // render without capability-gated extras.
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <CurrentUserContext.Provider
      value={{ user, loading, can: (capability) => hasCapability(user, capability) }}
    >
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser(): CurrentUserState {
  return useContext(CurrentUserContext);
}
