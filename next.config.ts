import type { NextConfig } from "next";

// Defensive check to prevent enabling dev auth bypass in production
const isProduction =
  process.env.NODE_ENV === "production" ||
  process.env.ENVIRONMENT === "production" ||
  process.env.APP_ENV === "production";

if (isProduction && process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true") {
  throw new Error(
    "CRITICAL CONFIGURATION ERROR: NEXT_PUBLIC_DEV_AUTH_BYPASS cannot be enabled in a production environment!"
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
