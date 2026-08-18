import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Redireciona chamadas /api/* para o backend em dev
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
