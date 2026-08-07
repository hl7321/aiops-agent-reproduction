import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

import { loadMergedConfig, toPublicConfig } from "./build/public-config.mjs";

const projectPath = fileURLToPath(new URL("../../config/project.json", import.meta.url));
const userPath = fileURLToPath(new URL("../../config/user.project.json", import.meta.url));
const mergedConfig = await loadMergedConfig(projectPath, userPath);
const publicConfig = toPublicConfig(mergedConfig);

export default defineConfig({
  plugins: [vue()],
  define: {
    __PUBLIC_CONFIG__: JSON.stringify(publicConfig),
  },
});
