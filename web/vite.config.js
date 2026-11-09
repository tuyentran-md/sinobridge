import { defineConfig } from "vite";
export default defineConfig({
  base: process.env.GITHUB_ACTIONS ? "/sinobridge/" : "/",
  build: { outDir: "dist", target: "es2022", sourcemap: false },
});
