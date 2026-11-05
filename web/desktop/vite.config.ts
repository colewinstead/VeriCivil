import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

import editionTools from "../../desktop/edition.cjs";

const edition = editionTools.getEdition();
export default defineConfig({
  root: fileURLToPath(new URL("./", import.meta.url)),
  publicDir: false,
  resolve: { alias: { "@": fileURLToPath(new URL("../", import.meta.url)) } },
  plugins: [react(), { name: "desktop-title", transformIndexHtml: html => html.replace("<title>Superelevation · VeriCivil Desktop Preview</title>", `<title>${edition.windowTitle}</title>`) }],
  define: { "process.env.NODE_ENV": '"production"', __DESKTOP_BRANDING__: JSON.stringify(edition) },
  build: { outDir: fileURLToPath(new URL(`../../desktop/${edition.appDirectory}/renderer`, import.meta.url)), emptyOutDir: true },
});
