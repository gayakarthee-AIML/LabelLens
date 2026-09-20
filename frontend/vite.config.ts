import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// LabelLens frontend build configuration.
// VITE_API_BASE_URL is read at runtime from import.meta.env — see .env.example.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "robots.txt"],
      manifest: {
        name: "LabelLens — Legal Metrology Compliance",
        short_name: "LabelLens",
        description:
          "AI-assisted Legal Metrology compliance and inspection platform for field inspectors and regulators.",
        theme_color: "#16213E",
        background_color: "#F7F4EE",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" }
        ]
      },
      workbox: {
        // App shell + static assets are precached. Inspection payloads themselves
        // are queued through IndexedDB (see src/services/offlineDb.ts), not the
        // Workbox cache, because they need structured retry/sync logic.
        globPatterns: ["**/*.{js,css,html,svg,png,ico}"],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkFirst",
            options: {
              cacheName: "labellens-api-cache",
              networkTimeoutSeconds: 4,
              cacheableResponse: { statuses: [0, 200] }
            }
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  server: {
    port: 5173,
    host: true,
    // Vite's dev server only trusts localhost/127.0.0.1 by default (a
    // DNS-rebinding protection) and rejects requests that arrive with any
    // other Host header — including ones forwarded through an ngrok tunnel,
    // which fail with "Blocked request. This host ... is not allowed."
    // `true` disables that check entirely. Fine for local dev/testing
    // (this is the same dev server already only reachable on your own
    // machine/LAN) — don't carry this into a real production deployment,
    // which wouldn't run `vite dev` anyway.
    allowedHosts: true,
    // Lets the frontend dev server proxy /api/* calls straight to the
    // FastAPI backend on the SAME machine, so the browser only ever talks
    // to ONE origin (this dev server) — no CORS needed, and critically,
    // only one public tunnel (ngrok/etc.) is needed when testing on a
    // phone, since the backend never needs to be exposed separately.
    // Target is fixed at the standard local backend port. If your backend
    // runs elsewhere, edit this directly rather than via an env var — vite.config.ts
    // runs under plain Node without @types/node in this project, so
    // process.env isn't typed here.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
