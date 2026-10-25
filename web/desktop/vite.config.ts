import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("./", import.meta.url)),
  publicDir: false,
  resolve: { alias: { "@": fileURLToPath(new URL("../", import.meta.url)) } },
  plugins: [react()],
  define: { "process.env.NODE_ENV": '"production"' },
  build: { outDir: fileURLToPath(new URL("../../desktop/app/renderer", import.meta.url)), emptyOutDir: true },
});
