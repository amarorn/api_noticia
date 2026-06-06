import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const repoRoot = path.resolve(__dirname, "..");

function resolveApiKey(mode: string): string {
  const root = loadEnv(mode, repoRoot, "");
  const local = loadEnv(mode, __dirname, "");
  return (
    local.VITE_API_KEY?.trim() ||
    root.VITE_API_KEY?.trim() ||
    root.API_KEY?.trim() ||
    ""
  );
}

export default defineConfig(({ mode }) => {
  const apiKey = resolveApiKey(mode);

  return {
    plugins: [react()],
    define: apiKey
      ? { "import.meta.env.VITE_API_KEY": JSON.stringify(apiKey) }
      : undefined,
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
          timeout: 900_000,
          proxyTimeout: 900_000,
        },
      },
    },
  };
});
