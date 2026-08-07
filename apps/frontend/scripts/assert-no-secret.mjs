import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import vue from "@vitejs/plugin-vue";
import { build } from "vite";

import { loadMergedConfig, toPublicConfig } from "../build/public-config.mjs";

const sentinel = "SENTINEL_SERVER_SECRET";
const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const temporaryRoot = await mkdtemp(join(tmpdir(), "super-ai-secret-build-"));
const projectPath = join(temporaryRoot, "project.json");
const userPath = join(temporaryRoot, "user.project.json");
const outDir = join(temporaryRoot, "dist");

try {
  await writeFile(
    projectPath,
    JSON.stringify({
      frontend: { title: "Sentinel build", apiBaseUrl: "/api" },
      analytics: { publicKey: "public-analytics" },
      llm: { apiKey: sentinel },
      cls: { secretKey: sentinel },
      mcp: { apiKey: sentinel },
      minio: { password: sentinel },
    }),
    "utf8",
  );
  await writeFile(userPath, "{}", "utf8");

  const mergedConfig = await loadMergedConfig(projectPath, userPath);
  const publicConfig = toPublicConfig(mergedConfig);
  await build({
    root: frontendRoot,
    configFile: false,
    plugins: [vue()],
    define: { __PUBLIC_CONFIG__: JSON.stringify(publicConfig) },
    build: { outDir, emptyOutDir: true },
  });

  for (const path of await listFiles(outDir)) {
    const contents = await readFile(path);
    if (contents.includes(Buffer.from(sentinel))) {
      throw new Error(`浏览器构建产物泄露 sentinel secret: ${path}`);
    }
  }
} finally {
  await rm(temporaryRoot, { recursive: true, force: true });
}

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listFiles(path));
    } else {
      files.push(path);
    }
  }
  return files;
}
