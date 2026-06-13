import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8200 (8000 is taken by another local app). Proxy API
// calls so the client can use same-origin relative paths and dodge CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8200",
      "/health": "http://localhost:8200",
    },
  },
});
