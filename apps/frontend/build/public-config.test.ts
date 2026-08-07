import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { loadMergedConfig, toPublicConfig } from "./public-config.mjs";

describe("public config", () => {
  it("递归合并时保留未覆盖的前端默认值", async () => {
    const directory = await mkdtemp(join(tmpdir(), "super-ai-config-"));
    const projectPath = join(directory, "project.json");
    const userPath = join(directory, "user.project.json");
    await writeFile(
      projectPath,
      JSON.stringify({ frontend: { title: "项目", apiBaseUrl: "/api" } }),
      "utf8",
    );
    await writeFile(userPath, JSON.stringify({ frontend: { title: "用户" } }), "utf8");

    const merged = await loadMergedConfig(projectPath, userPath);

    expect(merged).toEqual({ frontend: { title: "用户", apiBaseUrl: "/api" } });
  });

  it("只投影公开字段并排除服务端秘密", () => {
    const sentinel = "SENTINEL_SERVER_SECRET";
    const publicConfig = toPublicConfig({
      frontend: { title: "值班台", apiBaseUrl: "/api" },
      analytics: { publicKey: "public-analytics" },
      llm: { apiKey: sentinel },
      cls: { secretKey: sentinel },
      mcp: { apiKey: sentinel },
      minio: { password: sentinel },
    });

    expect(publicConfig).toEqual({
      title: "值班台",
      apiBaseUrl: "/api",
      analyticsPublicKey: "public-analytics",
    });
    expect(JSON.stringify(publicConfig)).not.toContain(sentinel);
  });
});
