import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// dev(:5173)에서 same-origin으로 게이트웨이(:8000)에 프록시 — WS 포함.
// 배포는 nginx가 동일 역할(정적 FE + /api 프록시).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, ws: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
