import type {
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  SseEvent,
} from "@super-ai/api-contracts";

export type AiopsTimelinePhase = "planner" | "executor" | "replanner" | "report" | "task";
export type AiopsTimelineStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface AiopsTimelineItem {
  readonly key: string;
  readonly phase: AiopsTimelinePhase;
  readonly status: AiopsTimelineStatus;
  readonly title: string;
  readonly summary: string;
  readonly timestamp: string | null;
  readonly collapsible: boolean;
  readonly detail: string | null;
}

export function buildLiveTimeline(events: readonly SseEvent[]): readonly AiopsTimelineItem[] {
  return events.filter((event) => event.channel === "aiops").map((event) => {
    switch (event.type) {
      case "task.status": {
        const summary = event.data.message ?? `任务状态：${event.data.status}`;
        return item(event.id, phaseFromMessage(summary), taskStatus(event.data.status), "诊断进度", summary,
          event.timestamp, false, null);
      }
      case "tool.call": {
        const lifecycle = event.data.lifecycle;
        const status = lifecycle === "failed" ? "failed"
          : lifecycle === "completed" ? "succeeded" : "running";
        const safeSummary = lifecycle === "started" ? "工具调用已开始"
          : lifecycle === "completed" ? "工具调用已完成"
            : lifecycle === "failed" ? (event.data.error?.message ?? "工具调用失败")
              : "工具正在返回结果";
        return item(event.id, "executor", status, `工具：${event.data.toolName}`, safeSummary,
          event.timestamp, true, "仅展示安全摘要；原始参数与工具输出不会在页面显示。");
      }
      case "reference.source":
        if (event.channel !== "aiops") {
          return item(event.id, "task", "running", "任务进度", "收到非诊断引用",
            event.timestamp, false, null);
        }
        return item(event.id, "executor", "succeeded", `证据：${event.data.source.title}`,
          event.data.source.excerpt, event.timestamp, true,
          `${event.data.source.kind} · ${event.data.source.source}`);
      case "report":
        return item(event.id, "report", "succeeded", "诊断报告", "报告已生成并持久化",
          event.timestamp, false, null);
      case "error":
        return item(event.id, "task", "failed", "诊断失败", event.data.error.message,
          event.timestamp, false, null);
      case "complete":
        return item(event.id, "task", event.data.finishReason === "stop" ? "succeeded"
          : event.data.finishReason === "cancelled" ? "cancelled" : "failed",
        "持久任务结束", completeLabel(event.data.finishReason), event.timestamp, false, null);
      case "content.delta":
      case "reasoning.delta":
        return item(event.id, "task", "running", "模型进度", "收到模型流式进度",
          event.timestamp, false, null);
    }
  });
}

export function buildPersistentExecutionChain(
  detail: DiagnosticDetailData | null,
  chain: DiagnosticEvidenceChainData | null,
): readonly AiopsTimelineItem[] {
  if (detail === null) return [];
  const planStatus: AiopsTimelineStatus = detail.task.status === "accepted" ? "pending"
    : detail.task.status === "running" ? "running"
      : detail.task.status;
  const plan = detail.task.currentPlan.map((step) => item(
    `plan:${detail.task.planVersion}:${step.position}`, "planner", planStatus,
    `计划 ${step.position + 1}：${step.toolName}`, step.purpose, detail.task.updatedAt,
    true, null,
  ));
  const steps = detail.steps.map((step) => item(
    `step:${step.id}`, step.toolName.toLowerCase().includes("report") ? "report" : "executor",
    step.status, `步骤 ${step.position + 1}：${step.toolName}`,
    `${step.resultSummary ?? step.errorMessage ?? "等待执行"} · 第 ${step.attempt} 次尝试${
      step.errorCategory === null ? "" : ` · ${step.errorCategory}`
    }`, step.completedAt ?? step.startedAt,
    true, step.errorMessage,
  ));
  const audits = (chain?.toolAudits ?? []).map((audit) => item(
    `audit:${audit.id}`, "executor", audit.status === "started" ? "running"
      : audit.status === "completed" ? "succeeded" : "failed", `审计：${audit.toolName}`,
    audit.resultSummary ?? audit.errorMessage ?? "工具调用记录", audit.completedAt ?? audit.startedAt,
    true, audit.errorMessage,
  ));
  return [...plan, ...steps, ...audits];
}

function item(
  key: string,
  phase: AiopsTimelinePhase,
  status: AiopsTimelineStatus,
  title: string,
  summary: string,
  timestamp: string | null,
  collapsible: boolean,
  detail: string | null,
): AiopsTimelineItem {
  return { key, phase, status, title, summary, timestamp, collapsible, detail };
}

function phaseFromMessage(message: string): AiopsTimelinePhase {
  const normalized = message.toLowerCase();
  if (/重规划|replan/u.test(normalized)) return "replanner";
  if (/计划|planner/u.test(normalized)) return "planner";
  if (/报告|report/u.test(normalized)) return "report";
  if (/执行|工具|executor/u.test(normalized)) return "executor";
  return "task";
}

function completeLabel(reason: "stop" | "error" | "cancelled"): string {
  if (reason === "stop") return "诊断已完成";
  if (reason === "cancelled") return "诊断已取消";
  return "诊断以错误结束";
}

function taskStatus(status: "queued" | "running" | "succeeded" | "failed" | "cancelled"):
AiopsTimelineStatus {
  return status === "queued" ? "pending" : status;
}
