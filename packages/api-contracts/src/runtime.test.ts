import { describe, expect, it } from "vitest";

import manifest from "../contract-manifest.json";
import type { ConfigurationCheckData, ProcessMetrics, ReadinessData } from "./runtime";

describe("runtime delivery contracts", () => {
  it("keeps dependency failures explicit and metrics process-scoped", () => {
    const readiness: ReadinessData = {
      status: "unavailable",
      dependencies: {
        sqlite: { name: "sqlite", status: "ready", latencyMs: 1, error: null },
        milvus: { name: "milvus", status: "unavailable", latencyMs: 2, error: "连接失败" },
        qwen: { name: "qwen", status: "ready", latencyMs: 3, error: null },
        mcp: { name: "mcp", status: "ready", latencyMs: 4, error: null },
      },
    };
    const config: ConfigurationCheckData = {
      status: "dependencies_unavailable",
      configuration: { status: "valid", sections: ["database", "llm"], error: null },
      dependencies: readiness.dependencies,
    };
    const metrics: ProcessMetrics = {
      scope: "process", requestCount: 3, failureCount: 1,
      totalDurationMs: 30, averageDurationMs: 10,
    };

    expect(config.dependencies?.milvus.status).toBe("unavailable");
    expect(metrics.scope).toBe("process");
  });

  it("registers public runtime paths before backend endpoints", () => {
    expect(manifest.openapi.paths["/ready"]).toMatchObject({
      method: "GET", operationId: "getRuntimeReadiness", errors: ["SYSTEM_UNAVAILABLE"],
    });
    expect(manifest.openapi.paths["/config/check"].successData).toBe("ConfigurationCheckData");
    expect(manifest.openapi.paths["/health/mcp"].successData).toBe("RuntimeDependencyResult");
    expect(manifest.openapi.paths["/metrics"].successData).toBe("ProcessMetrics");
  });
});
