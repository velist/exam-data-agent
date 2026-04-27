import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiUrl = env.VITE_API_URL || "https://ksapi.aipush.fun";

  return {
    define: {
      "import.meta.env.VITE_API_URL": JSON.stringify(apiUrl),
    },
    plugins: [react()],
    server: {
      proxy: {
        "/api": "http://172.10.10.51:8230",
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
    },
  };
});
