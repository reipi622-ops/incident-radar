import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // NEXT_PUBLIC_API_URL is set via docker-compose environment
  // Browser calls this directly, so localhost:8000 is correct (port is forwarded)
};

export default nextConfig;
