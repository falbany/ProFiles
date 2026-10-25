import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import fs from "node:fs";
import path from "node:path";

// The app version lives only in [project].version of the repo-root
// pyproject.toml; it is injected at build time as __APP_VERSION__ so the
// UI fallback (HeaderBar) never duplicates the string.
const pyproject = fs.readFileSync(
  path.resolve(__dirname, "../../../pyproject.toml"),
  "utf-8",
);
const appVersion =
  /^version\s*=\s*"([^"]+)"/m.exec(pyproject)?.[1] ?? "0.0.0-dev";

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "robots.txt"],
      manifest: {
        name: "ProFiles Launcher",
        short_name: "ProFiles",
        description: "Modern desktop & test bench file launcher",
        theme_color: "#0f172a",
        background_color: "#020617",
        display: "standalone",
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
