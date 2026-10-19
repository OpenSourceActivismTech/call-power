import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/user": "http://localhost:8000",
      "/admin/user": "http://localhost:8000",
      "/call": "http://localhost:8000",
      "/political_data": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  build: {
    outDir: "../django_app/static/admin",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "index.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
