import type {
  ActiveAlertsData,
  BackgroundJob,
  CreateDiagnosticRequest,
  DiagnosticCaseDetailData,
  DiagnosticCaseListData,
  DiagnosticCreateData,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  DiagnosticListData,
  KnowledgeBaseListData,
  SseEvent,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";
import type { SseClient } from "../transport/sseClient";

export interface AiopsClient {
  listActiveAlerts(): Promise<ApiResult<ActiveAlertsData>>;
  createDiagnostic(body: CreateDiagnosticRequest): Promise<ApiResult<DiagnosticCreateData>>;
  listDiagnostics(): Promise<ApiResult<DiagnosticListData>>;
  getDiagnostic(id: string): Promise<ApiResult<DiagnosticDetailData>>;
  getEvidenceChain(id: string): Promise<ApiResult<DiagnosticEvidenceChainData>>;
  streamDiagnostic(id: string, afterSequence?: number): AsyncIterable<SseEvent>;
  cancelBackgroundJob(id: string): Promise<ApiResult<BackgroundJob>>;
  listCases(): Promise<ApiResult<DiagnosticCaseListData>>;
  getCase(id: string): Promise<ApiResult<DiagnosticCaseDetailData>>;
  listKnowledgeBases(): Promise<ApiResult<KnowledgeBaseListData>>;
}

export function createAiopsClient(api: ApiClient, sse: SseClient): AiopsClient {
  return {
    listActiveAlerts: () => api.request<ActiveAlertsData>("/aiops/alerts/active"),
    createDiagnostic: (body) => api.request<DiagnosticCreateData>("/aiops/diagnostics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    listDiagnostics: () => api.request<DiagnosticListData>("/aiops/diagnostics"),
    getDiagnostic: (id) => api.request<DiagnosticDetailData>(
      `/aiops/diagnostics/${encodeURIComponent(id)}`,
    ),
    getEvidenceChain: (id) => api.request<DiagnosticEvidenceChainData>(
      `/aiops/diagnostics/${encodeURIComponent(id)}/evidence-chain`,
    ),
    streamDiagnostic: (id, afterSequence = 0) => sse.stream(
      `/aiops/diagnostics/${encodeURIComponent(id)}:stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ afterSequence }),
      },
    ),
    cancelBackgroundJob: (id) => api.request<BackgroundJob>(
      `/background-jobs/${encodeURIComponent(id)}:cancel`,
      { method: "POST" },
    ),
    listCases: () => api.request<DiagnosticCaseListData>("/aiops/diagnostic-cases"),
    getCase: (id) => api.request<DiagnosticCaseDetailData>(
      `/aiops/diagnostic-cases/${encodeURIComponent(id)}`,
    ),
    listKnowledgeBases: () => api.request<KnowledgeBaseListData>("/knowledge-bases"),
  };
}
