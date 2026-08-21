import type { ActiveAlert } from "./alerts";
import type { BackgroundJob } from "./background-jobs";
import type { AgentToolCallAudit } from "./chat";
import type { JsonValue } from "./http";

export type DiagnosticStatus = "accepted" | "running" | "succeeded" | "failed" | "cancelled";
export type DiagnosticStepStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";
export type DiagnosticEvidenceKind = "alert" | "knowledge" | "log" | "metric";
export type DiagnosticReportGenerationMode = "model" | "fallback";

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

export interface DiagnosticEvidenceChainData {
  readonly taskId: string;
  readonly evidence: readonly DiagnosticEvidence[];
  readonly reportEvidenceLinks: readonly ReportEvidenceLink[];
  readonly toolAudits: readonly AgentToolCallAudit[];
}
