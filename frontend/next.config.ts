import path from "node:path";

import type { NextConfig } from "next";

const root = path.resolve(__dirname);

const nextConfig: NextConfig = {
  // Multi-stage Alpine Docker build copies the traced standalone server (Task 6.5).
  output: "standalone",
  // Pin the workspace root so standalone tracing is scoped to this app, not a parent lockfile.
  outputFileTracingRoot: root,
  turbopack: { root },
};

export default nextConfig;
