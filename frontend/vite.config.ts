import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // All /api requests are forwarded to the Flask backend running on :5001.
      // changeOrigin rewrites the Host header to 127.0.0.1:5001 so that
      // Flask's is_local_request() always recognises the dev-server as local,
      // enabling download, check-link, clipboard, browse-folder, etc. — the
      // exact same feature-set as the packaged .app.
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
    },
  },
});
