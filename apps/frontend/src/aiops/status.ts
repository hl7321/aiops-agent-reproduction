import type { DiagnosticTask } from "@super-ai/api-contracts";

/**
 * 证据不足、未能得出可信结论的诊断也会落到 failed，但它与系统故障不是一回事。
 * 后端用这个稳定错误码区分，前端据此给出可读的措辞，避免把"没得出结论"显示成"成功"。
 */
export const INSUFFICIENT_EVIDENCE_CODE = "SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE";

const TASK_STATUS_LABELS: Record<DiagnosticTask["status"], string> = {
  accepted: "已受理",
  running: "运行中",
  succeeded: "已成功",
  failed: "失败",
  cancelled: "已取消",
};

/** 诊断终态展示文案：先看"结论可不可信"，再看流程状态。 */
export function diagnosticStatusLabel(
  task: Pick<DiagnosticTask, "status" | "failureCode"> | null | undefined,
): string {
  if (task === null || task === undefined) return "未选择";
  if (task.failureCode === INSUFFICIENT_EVIDENCE_CODE) return "证据不足";
  return TASK_STATUS_LABELS[task.status];
}
