export type RuntimeDependencyName = "sqlite" | "milvus" | "qwen" | "mcp";
export type RuntimeDependencyStatus = "ready" | "unavailable";

export interface RuntimeDependencyResult {
  name: RuntimeDependencyName;
  status: RuntimeDependencyStatus;
  latencyMs: number;
  error: string | null;
}

export interface RuntimeDependencies {
  sqlite: RuntimeDependencyResult;
  milvus: RuntimeDependencyResult;
  qwen: RuntimeDependencyResult;
  mcp: RuntimeDependencyResult;
}

export interface ReadinessData {
  status: RuntimeDependencyStatus;
  dependencies: RuntimeDependencies;
}

export interface ConfigurationStatus {
  status: "valid" | "invalid";
  sections: string[];
  error: string | null;
}

export interface ConfigurationCheckData {
  status: "ready" | "configuration_invalid" | "dependencies_unavailable";
  configuration: ConfigurationStatus;
  dependencies: RuntimeDependencies | null;
}

export interface ProcessMetrics {
  scope: "process";
  requestCount: number;
  failureCount: number;
  totalDurationMs: number;
  averageDurationMs: number;
}
