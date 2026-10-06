import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// as variáveis vêm do .env da raiz do projeto (dev local) ou do ambiente (docker build / Coolify)
export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(__dirname, "../.."), "");
  const env = (name, fallback = "") => process.env[name] ?? rootEnv[name] ?? fallback;

  return {
    plugins: [react()],
    define: {
      "import.meta.env.VITE_RASPBERRY_WS_URL": JSON.stringify(env("RASPBERRY_WS_URL")),
    },
    server: {
      proxy: {
        "/api": {
          target: `http://localhost:${env("BACKEND_PORT", "8000")}`,
          changeOrigin: true,
        },
      },
    },
  };
});
