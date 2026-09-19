import type { ActiveAlert } from "./alerts";
import type { BackgroundJob } from "./background-jobs";
import type { AgentToolCallAudit } from "./chat";
import type { JsonValue } from "./http";
import type { KnowledgeDocument } from "./knowledge";
import type { DocumentIndexTask } from "./document-indexing";

export type DiagnosticStatus = "accepted" | "running" | "succeeded" | "failed" | "cancelled";
export type DiagnosticStepStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

/**
 * 诊断证据种类的运行时事实来源。
 *
 * 类型与运行时校验都必须引用这一份清单：SSE guard 需要真实存在的值做判断，
 * 而 TypeScript 类型在运行时不存在，因此只能由常量派生类型，不能反向维护两份。
 */
export const DIAGNOSTIC_EVIDENCE_KINDS = [
  "alert",
  "knowledge",
  "log",
  "log_hit",
  "log_context",
  "query_artifact",
  "metric",
] as const;

export type DiagnosticEvidenceKind = (typeof DIAGNOSTIC_EVIDENCE_KINDS)[number];
export type DiagnosticReportGenerationMode = "model" | "fallback";
export type DiagnosticReportTrustState =
  | "verified_evidence"
  | "insufficient_evidence"
  | "execution_failed";
export type DiagnosticToolErrorCategory =
  | "input_validation"
  | "output_validation"
  | "empty_result"
  | "timeout"
  | "rate_limited"
  | "transport"
  | "provider_unavailable"
  | "configuration"
  | "permission"
  | "owner_scope"
  | "tool_not_allowed"
  | "schema_incompatible"
  | "permanent";

export interface DiagnosticPlanStep {
  readonly position: number;
  readonly toolName: string;
  readonly purpose: string;
  readonly arguments: Readonly<Record<string, JsonValue>>;
}

export interface DiagnosticTask {
  readonly id: string;
  readonly ownerUserId: string;
  readonly status: DiagnosticStatus;
  readonly query: string | null;
  readonly alerts: readonly ActiveAlert[];
  readonly currentPlan: readonly DiagnosticPlanStep[];
  readonly planVersion: number;
  readonly replanCount: number;
  readonly failureCode: string | null;
  readonly failureReason: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
}

export interface DiagnosticStep {
  readonly id: string;
  readonly diagnosticTaskId: string;
  readonly planVersion: number;
  readonly position: number;
  readonly attempt: number;
  readonly toolName: string;
  readonly arguments: Readonly<Record<string, JsonValue>>;
  readonly status: DiagnosticStepStatus;
  readonly resultSummary: string | null;
  readonly errorMessage: string | null;
  readonly errorCategory: DiagnosticToolErrorCategory | null;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly createdAt: string;
}

export interface DiagnosticEvidence {
  readonly id: string;
  readonly diagnosticTaskId: string;
  readonly diagnosticStepId: string | null;
  readonly toolCallId: string | null;
  readonly kind: DiagnosticEvidenceKind;
  readonly source: string;
  readonly title: string;
  readonly summary: string;
  readonly content: string;
  readonly metadata: Readonly<Record<string, JsonValue>>;
  readonly observedAt: string | null;
  readonly createdAt: string;
}

export interface DiagnosticEvidenceReference {
  readonly evidenceId: string;
  readonly kind: DiagnosticEvidenceKind;
  readonly source: string;
  readonly title: string;
  readonly excerpt: string;
  readonly metadata: Readonly<Record<string, JsonValue>>;
}

export interface DiagnosticReport {
  readonly id: string;
  readonly diagnosticTaskId: string;
  readonly revision: number;
  readonly markdown: string;
  readonly generationMode: DiagnosticReportGenerationMode;
  readonly uncertainty: boolean;
  readonly trustState: DiagnosticReportTrustState;
  readonly createdAt: string;
}

export interface ReportEvidenceLink {
  readonly id: string;
  readonly diagnosticTaskId: string;
  readonly reportId: string;
  readonly evidenceId: string;
  readonly claimKey: string;
  readonly section: string;
  readonly position: number;
}

export interface CreateDiagnosticRequest {
  readonly alerts: readonly ActiveAlert[];
  readonly query?: string;
}

export interface DiagnosticStreamRequest {
  readonly afterSequence?: number;
}

export interface DiagnosticCreateData {
  readonly task: DiagnosticTask;
  readonly backgroundJob: BackgroundJob;
}

export interface DiagnosticListData { readonly items: readonly DiagnosticTask[]; }

export interface DiagnosticDetailData {
  readonly task: DiagnosticTask;
  readonly backgroundJob: BackgroundJob;
  readonly steps: readonly DiagnosticStep[];
  readonly report: DiagnosticReport | null;
}

/** 一次诊断的阶段耗时：受理 / 规划 / 执行 / 报告。 */
export interface DiagnosticExecutionStage {
  readonly name: string;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
}

/** 单次尝试的真实记录；参数只给键名，不给取值。 */
export interface DiagnosticExecutionAttempt {
  readonly attempt: number;
  readonly status: DiagnosticStepStatus;
  readonly argumentKeys: readonly string[];
  readonly failureClass: string | null;
  readonly errorCategory: DiagnosticToolErrorCategory | null;
  readonly errorMessage: string | null;
  readonly resultSummary: string | null;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
}

export interface DiagnosticExecutionEvidenceRef {
  readonly evidenceId: string;
  readonly kind: DiagnosticEvidenceKind;
  readonly summary: string;
}

/** 一条计划步骤的执行对账：计划意图 + 实际尝试 + 真实产出。 */
export interface DiagnosticExecutionStep {
  readonly position: number;
  readonly toolName: string;
  readonly purpose: string;
  readonly executed: boolean;
  readonly status: DiagnosticStepStatus;
  readonly resultSummary: string | null;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
  readonly attempts: readonly DiagnosticExecutionAttempt[];
  readonly producedEvidence: readonly DiagnosticExecutionEvidenceRef[];
}

/** 后端组装的完整执行结果，供"一次点击发生了什么"展示。 */
export interface DiagnosticExecutionResult {
  readonly taskId: string | null;
  readonly createdAt: string | null;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
  readonly stages: readonly DiagnosticExecutionStage[];
  readonly plan: readonly DiagnosticExecutionStep[];
  readonly evidenceByKind: Readonly<Record<string, number>>;
}

export interface DiagnosticEvidenceChainData {
  readonly taskId: string;
  readonly evidence: readonly DiagnosticEvidence[];
  readonly reportEvidenceLinks: readonly ReportEvidenceLink[];
  readonly toolAudits: readonly AgentToolCallAudit[];
  readonly executionResult: DiagnosticExecutionResult | null;
}

export interface DiagnosticCase {
  readonly id: string;
  readonly ownerUserId: string;
  readonly taskId: string;
  readonly reportId: string;
  readonly documentId: string;
  readonly indexTaskId: string;
  readonly alertName: string;
  readonly service: string;
  readonly keywords: readonly string[];
  readonly rootCause: string;
  readonly remediation: string;
  readonly summary: string;
  readonly evidenceIds: readonly string[];
  readonly incidentFingerprint: string | null;
  readonly knowledgeFingerprint: string | null;
  readonly fingerprintVersion: string | null;
  readonly promotionStatus: "legacy" | "canonical";
  readonly createdAt: string;
}

export interface DiagnosticCasePromotionCandidate {
  readonly item: DiagnosticCase;
  readonly similarityScore: number;
}

export interface PromoteDiagnosticCaseRequest {
  readonly resolution?: "create_new" | "merge";
  readonly candidateCaseId?: string;
}

export interface DiagnosticCasePromotionResult {
  readonly status: "created" | "existing" | "needs_review" | "merged";
  readonly item: DiagnosticCase | null;
  readonly candidates: readonly DiagnosticCasePromotionCandidate[];
}

export interface DiagnosticCaseListData { readonly items: readonly DiagnosticCase[]; }
export interface DiagnosticCaseDetailData { readonly item: DiagnosticCase; }
export interface SaveDiagnosisToKnowledgeData {
  readonly document: KnowledgeDocument;
  readonly indexTask: DocumentIndexTask;
}
