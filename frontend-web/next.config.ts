import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
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
