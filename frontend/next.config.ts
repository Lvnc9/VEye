import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev only: the API (NEXT_PUBLIC_API_BASE_URL) and its host-only session cookies live on
  // `localhost`, so a page opened on 127.0.0.1 would lose hydration (Next blocks its dev
  // resources) and could never keep a login. Send it to `localhost` instead.
  async redirects() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "127.0.0.1(:\\d+)?" }],
        destination: "http://localhost:3000/:path*",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
