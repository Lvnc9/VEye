import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev only: the API (NEXT_PUBLIC_API_BASE_URL) and its host-only session cookies live on
  // `localhost`, so a page opened on 127.0.0.1 would lose hydration (Next blocks its dev
  // resources) and could never keep a login. Send it to the stack's own frontend address instead
  // (FRONTEND_BASE_URL — e.g. http://a1.localhost:3101 for a side-by-side stack; Next already
  // allows `*.localhost` as a dev origin, so no allowedDevOrigins entry is needed).
  async redirects() {
    if (process.env.NODE_ENV === "production") return [];
    const frontend = (process.env.FRONTEND_BASE_URL || "http://localhost:3000").replace(/\/+$/, "");
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "127.0.0.1(:\\d+)?" }],
        destination: `${frontend}/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
