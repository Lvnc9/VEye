"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Root route. middleware.ts already redirects unauthenticated visitors to
 * /login, so by the time this renders the visitor is authenticated — just
 * send them on to the dashboard.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return null;
}
