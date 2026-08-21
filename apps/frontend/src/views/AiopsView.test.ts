// @vitest-environment happy-dom
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ActiveAlert,
  BackgroundJob,
  DiagnosticCase,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  DiagnosticTask,
} from "@super-ai/api-contracts";

import { useAiopsStore } from "../stores/aiops";
import AiopsView from "./AiopsView.vue";

const ALERT: ActiveAlert = {
  alertName: "HighLatency", service: "checkout", severity: "critical", status: "firing",
  startsAt: "now", labels: {}, annotations: {}, source: { name: "prometheus", type: "prometheus-v1" },
  rawContext: { raw: "raw-alert-json-must-not-render" },
};
const TASK: DiagnosticTask = {
  id: "task-1", ownerUserId: "owner", status: "succeeded", query: "排查 checkout", alerts: [ALERT],
  currentPlan: [], planVersion: 1, replanCount: 1, failureCode: null, failureReason: null,
  createdAt: "now", updatedAt: "later", startedAt: "now", completedAt: "later",
};
const JOB: BackgroundJob = {
  id: "job-1", ownerUserId: "owner", kind: "aiops_diagnosis", status: "succeeded", payload: {},
  attempt: 1, maxAttempts: 3, timeoutSeconds: 600, availableAt: "now", createdAt: "now", updatedAt: "later",
};
const DETAIL: DiagnosticDetailData = {
  task: TASK, backgroundJob: JOB, steps: [{
    id: "step-1", diagnosticTaskId: TASK.id, planVersion: 1, position: 0, attempt: 1,
    toolName: "SearchLog", arguments: {}, status: "succeeded", resultSummary: "找到日志",
    errorMessage: null, startedAt: "now", completedAt: "later", createdAt: "now",
  }], report: {
    id: "report-1", diagnosticTaskId: TASK.id, revision: 1,
    markdown: "# 告警分析报告\n<img src=x onerror=alert(1)>\n## 📊 结论\n证据不足，仍存在不确定性。",
    generationMode: "fallback", uncertainty: true, createdAt: "later",
  },
};
const CHAIN: DiagnosticEvidenceChainData = {
  taskId: TASK.id,
  evidence: [{ id: "e-1", diagnosticTaskId: TASK.id, diagnosticStepId: null, toolCallId: null,
    kind: "log", source: "CLS", title: "错误日志", summary: "发现超时", content: "private-full-log",
    metadata: { secret: "raw-evidence-json" }, observedAt: "now", createdAt: "now" }],
  reportEvidenceLinks: [{ id: "l-1", diagnosticTaskId: TASK.id, reportId: "report-1",
    evidenceId: "e-1", claimKey: "root-cause", section: "根因", position: 0 }],
  toolAudits: [],
};
const CASE: DiagnosticCase = {
  id: "case-1", ownerUserId: "owner", taskId: TASK.id, reportId: "report-1", documentId: "doc-1",
  indexTaskId: "index-1", alertName: "HighLatency", service: "checkout", keywords: ["timeout"],
  rootCause: "依赖超时", remediation: "检查依赖", summary: "checkout 超时案例", evidenceIds: ["e-1"], createdAt: "now",
};

beforeEach(() => setActivePinia(createPinia()));

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/aiops", component: AiopsView },
    { path: "/knowledge", name: "knowledge", component: { template: "<div />" } },
  ] });
  await router.push("/aiops");
  await router.isReady();
  const store = useAiopsStore();
  store.history = [TASK]; store.activeAlerts = [ALERT]; store.cases = [CASE];
  store.activeDetail = DETAIL; store.evidenceChain = CHAIN; store.selectedCase = CASE;
  store.initialize = vi.fn(async () => undefined); store.reset = vi.fn();
  store.createDiagnostic = vi.fn(async () => undefined);
  return { wrapper: mount(AiopsView, { global: {
    plugins: [router],
    stubs: { UserFeedbackControl: { template: '<i class="feedback-control-stub" />' } },
  } }), store, router };
}

describe("AiopsView", () => {
  it("呈现固定三栏、双状态、持久证据与安全 Markdown", async () => {
    const { wrapper } = await mountView();
    await flushPromises();

    expect(wrapper.findAll(".aiops-column")).toHaveLength(3);
    expect(wrapper.text()).toContain("诊断：已成功 (succeeded)");
    expect(wrapper.text()).toContain("后台任务：已成功 (succeeded)");
    expect(wrapper.text()).toContain("证据不足，仍存在不确定性");
    expect(wrapper.text()).toContain("来源任务");
    expect(wrapper.text()).toContain("report-1");
    expect(wrapper.find(".aiops-report-scroll").exists()).toBe(true);
    expect(wrapper.find(".right-scroll").exists()).toBe(true);
    expect(wrapper.find(".aiops-report-scroll img").exists()).toBe(false);
    expect(wrapper.find(".aiops-report-scroll script").exists()).toBe(false);
    expect(wrapper.find(".aiops-report-scroll").html()).toContain("&lt;img");
    expect(wrapper.text()).not.toContain("raw-alert-json-must-not-render");
    expect(wrapper.text()).not.toContain("raw-evidence-json");
    expect(wrapper.text()).not.toContain("private-full-log");
    expect(wrapper.findAll(".feedback-control-stub")).toHaveLength(2);
  });

  it("从真实告警预填，也允许只用 query 创建且不生成 context", async () => {
    const { wrapper, store } = await mountView();
    await flushPromises();
    await wrapper.get("#diagnosis-query").setValue("仅手工排查");
    await wrapper.get(".diagnosis-form").trigger("submit");
    expect(store.createDiagnostic).toHaveBeenCalledWith("仅手工排查", null);

    await wrapper.get("#diagnosis-query").setValue("");
    await wrapper.get(".alert-row").trigger("click");
    expect((wrapper.get("#diagnosis-query").element as HTMLTextAreaElement).value).toContain("HighLatency");
    await wrapper.get(".diagnosis-form").trigger("submit");
    expect(store.createDiagnostic).toHaveBeenLastCalledWith(expect.stringContaining("HighLatency"), ALERT);
  });

  it("显示断流恢复提示与显式重新订阅，不伪装成功", async () => {
    const { wrapper, store } = await mountView();
    store.activeDetail = { ...DETAIL, task: { ...TASK, status: "running" },
      backgroundJob: { ...JOB, status: "running" } };
    store.streamDisconnected = true;
    store.streamError = "实时流已断开，已从服务器恢复持久状态";
    store.subscribeActive = vi.fn(async () => undefined);
    await flushPromises();

    expect(wrapper.text()).toContain("实时流已断开");
    await wrapper.get("button").trigger("focus");
    const subscribe = wrapper.findAll("button").find((button) => button.text().includes("手动重新订阅"));
    expect(subscribe).toBeDefined();
    await subscribe?.trigger("click");
    expect(store.subscribeActive).toHaveBeenCalledOnce();
  });

  it("案例文档使用服务器解析的 owner 知识库与 document 路由参数", async () => {
    const { wrapper, store, router } = await mountView();
    store.knowledgeDocumentTarget = vi.fn(async () => ({
      knowledgeBaseId: "kb-owner", documentId: "doc-1",
    }));
    await flushPromises();
    const open = wrapper.findAll("button").find((button) => button.text().includes("打开 owner 知识文档"));
    await open?.trigger("click");
    await flushPromises();

    expect(router.currentRoute.value.name).toBe("knowledge");
    expect(router.currentRoute.value.query).toEqual({
      knowledgeBaseId: "kb-owner", documentId: "doc-1",
    });
  });
});
