import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/reports/client-data-access",
        destination: "/clients",
        permanent: false,
      },
      {
        source: "/reports/client-data-access/:clientSlug",
        destination: "/clients/:clientSlug/data",
        permanent: false,
      },
      {
        source: "/reports/:clientSlug",
        destination: "/clients/:clientSlug/reports",
        permanent: false,
      },
    ];
  },
  turbopack: {
    root: path.join(__dirname, ".."),
  },
  experimental: {
    /**
     * Allow imports from sibling workspaces (e.g., ../lib for shared Composer code).
     */
    externalDir: true,
  },
  /**
   * Ensure output tracing includes the monorepo root so externalDir modules are bundled on Render.
   */
  outputFileTracingRoot: path.join(__dirname, ".."),
};

export default nextConfig;
