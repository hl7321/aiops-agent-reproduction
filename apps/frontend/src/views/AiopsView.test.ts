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
import { useUserFeedbackStore } from "../stores/userFeedback";
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
    errorCategory: null,
  }], report: {
    id: "report-1", diagnosticTaskId: TASK.id, revision: 1,
    markdown: "# 告警分析报告\n<img src=x onerror=alert(1)>\n## 📊 结论\n证据不足，仍存在不确定性。",
    generationMode: "fallback", uncertainty: true, trustState: "insufficient_evidence",
    createdAt: "later",
  },
};
const CHAIN: DiagnosticEvidenceChainData = {
  taskId: TASK.id,
  evidence: [{ id: "e-1", diagnosticTaskId: TASK.id, diagnosticStepId: null, toolCallId: null,
    kind: "log_context", source: "DescribeLogContext", title: "错误日志上下文", summary: "发现超时前后序列", content: "private-full-log",
    metadata: { secret: "raw-evidence-json" }, observedAt: "now", createdAt: "now" }],
  reportEvidenceLinks: [{ id: "l-1", diagnosticTaskId: TASK.id, reportId: "report-1",
    evidenceId: "e-1", claimKey: "root-cause", section: "根因", position: 0 }],
  toolAudits: [],
  executionResult: {
    taskId: TASK.id, createdAt: "now", startedAt: "now", completedAt: "later",
    durationMs: 12_000,
    stages: [
      { name: "受理", startedAt: "now", completedAt: "now", durationMs: 200 },
      { name: "规划", startedAt: "now", completedAt: "now", durationMs: 4_000 },
      { name: "执行", startedAt: "now", completedAt: "now", durationMs: 6_000 },
      { name: "报告", startedAt: "now", completedAt: "later", durationMs: 1_800 },
    ],
    plan: [{
      position: 0, toolName: "SearchLog", purpose: "检索 checkout 超时日志",
      executed: true, status: "succeeded", resultSummary: "[log_hit] 命中 4 条",
      startedAt: "now", completedAt: "now", durationMs: 6_000,
      attempts: [{
        attempt: 1, status: "succeeded", argumentKeys: ["Query", "Region", "TopicId"],
        failureClass: null, errorCategory: null, errorMessage: null,
        resultSummary: "[log_hit] 命中 4 条", startedAt: "now", completedAt: "now",
        durationMs: 6_000,
      }],
      producedEvidence: [{ evidenceId: "e-1", kind: "log_context", summary: "发现超时前后序列" }],
    }],
    evidenceByKind: { log_context: 1 },
  },
};
const CASE: DiagnosticCase = {
  id: "case-1", ownerUserId: "owner", taskId: TASK.id, reportId: "report-1", documentId: "doc-1",
  indexTaskId: "index-1", alertName: "HighLatency", service: "checkout", keywords: ["timeout"],
  rootCause: "依赖超时", remediation: "检查依赖", summary: "checkout 超时案例", evidenceIds: ["e-1"], createdAt: "now",
  incidentFingerprint: "incident-v1", knowledgeFingerprint: "knowledge-v1",
  fingerprintVersion: "v1", promotionStatus: "canonical",
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
    expect(wrapper.text()).toContain("证据不足，不可沉淀");
    expect(wrapper.text()).toContain("log_context");
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
    // 步骤级反馈控件已移除（一个 3 步诊断会有 3 个点赞按钮，太噪）；只保留报告级反馈。
    expect(wrapper.findAll(".feedback-control-stub")).toHaveLength(1);
    // 执行总账展示一次点击的全过程：阶段耗时 + 逐步对账 + 总耗时。
    expect(wrapper.text()).toContain("执行总账");
    expect(wrapper.text()).toContain("总耗时");
    expect(wrapper.text()).toContain("规划");
    expect(wrapper.text()).toContain("步骤 1：SearchLog");
    expect(wrapper.text()).toContain("第 1 次尝试");
    expect(wrapper.text()).toContain("证据统计");
  });

  it("运行中的诊断用本地秒表持续显示已进行时长，而不是空白或只在结束后才有数字", async () => {
    const { wrapper, store } = await mountView();
    await flushPromises();
    // 用真实时间戳而不是 "now"：秒表靠 Date.parse 判断，占位字符串解析不出时间会退化成"—"。
    const startedAt = new Date(Date.now() - 12_000).toISOString();
    store.evidenceChain = {
      ...CHAIN,
      executionResult: {
        ...CHAIN.executionResult!,
        startedAt, completedAt: null, durationMs: null,
        stages: [
          { name: "受理", startedAt, completedAt: startedAt, durationMs: 200 },
          { name: "规划", startedAt, completedAt: startedAt, durationMs: 4_000 },
          { name: "执行", startedAt, completedAt: null, durationMs: null },
          { name: "报告", startedAt: null, completedAt: null, durationMs: null },
        ],
        plan: [{
          position: 0, toolName: "SearchLog", purpose: "检索 checkout 超时日志",
          executed: true, status: "running", resultSummary: null,
          startedAt, completedAt: null, durationMs: null,
          attempts: [{
            attempt: 1, status: "running", argumentKeys: ["Query"], failureClass: null,
            errorCategory: null, errorMessage: null, resultSummary: null,
            startedAt, completedAt: null, durationMs: null,
          }],
          producedEvidence: [],
        }],
      },
    };
    await flushPromises();

    // 正在跑的是"执行"阶段，而不是时间线里最后那一段还没开始的"报告"。
    expect(wrapper.text()).toContain("进行中：执行");
    expect(wrapper.text()).toContain("步骤 1：SearchLog");
    expect(wrapper.text()).toContain("已进行");
    expect(wrapper.text()).toContain("总耗时");
    wrapper.unmount();
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

  it("中栏三段可以拉动调整高度，且只在这两段之间一增一减", async () => {
    const { wrapper } = await mountView();
    await flushPromises();
    const layout = (): string => wrapper.get(".center-body").attributes("data-layout") ?? "";
    // happy-dom 不排版，clientHeight 恒为 0；这里给一个真实高度让换算成立。
    Object.defineProperty(wrapper.get(".center-body").element, "clientHeight",
      { value: 900, configurable: true });
    expect(wrapper.findAll('[role="separator"]')).toHaveLength(2);
    const before = layout().split("/");

    // 向下拖：上面这段变高、下面这段等量变矮，第三段不动。
    await wrapper.get('[data-splitter="report-ledger"]').trigger("keydown", { key: "ArrowDown" });
    const after = layout().split("/");
    expect(Number(after[0])).toBeGreaterThan(Number(before[0]));
    expect(Number(after[1])).toBeLessThan(Number(before[1]));
    expect(after[2]).toBe(before[2]);
    expect(Number(after[0]) + Number(after[1])).toBeCloseTo(
      Number(before[0]) + Number(before[1]), 2,
    );
  });

  it("沉淀案例摊开来源报告的反馈内容，同一时间只展开一份且能收起", async () => {
    const userFeedback = useUserFeedbackStore();
    // 反馈保存在"来源报告"这个目标下，案例详情按键名取出来展示。
    userFeedback.itemsByKey = { "diagnostic_report:report-1:": {
      id: "feedback-1", targetType: "diagnostic_report", targetId: "report-1", subjectId: null,
      rating: "positive", reason: "incorrect", comment: "根因里的服务名写错了",
      correction: "应该是 checkout-service", createdAt: "now", updatedAt: "later",
    } };
    const second: DiagnosticCase = {
      ...CASE, id: "case-2", taskId: "task-2", reportId: "report-2", alertName: "DiskFull",
    };
    const { wrapper, store } = await mountView();
    store.cases = [CASE, second];
    // 视图会在选中案例后去服务器补一条"来源报告反馈"，这里用桩替代，测试保持离线。
    userFeedback.load = vi.fn(async () => undefined);
    await flushPromises();

    // 初始展开 mountView 选中的那一条：反馈的四个字段都在，且有收起入口。
    expect(wrapper.findAll(".case-detail")).toHaveLength(1);
    expect(wrapper.text()).toContain("用户反馈");
    expect(wrapper.text()).toContain("赞同");
    expect(wrapper.text()).toContain("incorrect");
    expect(wrapper.text()).toContain("根因里的服务名写错了");
    expect(wrapper.text()).toContain("应该是 checkout-service");
    expect(wrapper.find('[data-action="close-case"]').exists()).toBe(true);

    // 换一条：详情跟着走，但始终只有一份。
    store.selectCase = vi.fn(async (id: string) => {
      store.selectedCase = id === second.id ? second : CASE;
    });
    const rows = wrapper.findAll(".case-row");
    await rows[1]?.trigger("click");
    await flushPromises();
    expect(store.selectedCase?.id).toBe(second.id);
    expect(wrapper.findAll(".case-detail")).toHaveLength(1);

    // 再点同一条 = 收起，不能"打开就收不起来"。
    await rows[1]?.trigger("click");
    await flushPromises();
    expect(store.selectedCase).toBeNull();
    expect(wrapper.findAll(".case-detail")).toHaveLength(0);
  });

  it("只有 verified 且正向反馈的报告可显式提升，并展示相似候选决策", async () => {
    const feedback = useUserFeedbackStore();
    feedback.itemsByKey = { "diagnostic_report:report-1:": {
      id: "feedback-1", targetType: "diagnostic_report", targetId: "report-1", subjectId: null,
      rating: "positive", reason: null, comment: "已人工验证", correction: null,
      createdAt: "now", updatedAt: "now",
    } };
    const { wrapper, store } = await mountView();
    store.activeDetail = { ...DETAIL, report: { ...DETAIL.report!, generationMode: "model",
      uncertainty: false, trustState: "verified_evidence" } };
    store.promotionCandidates = [{ item: CASE, similarityScore: 0.82 }];
    store.promoteActive = vi.fn(async () => undefined);
    store.resolvePromotion = vi.fn(async () => undefined);
    await flushPromises();

    expect(wrapper.text()).toContain("可信证据已验证");
    await wrapper.get('[data-action="promote-case"]').trigger("click");
    expect(store.promoteActive).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("相似案例 82%");
    await wrapper.get('[data-action="merge-case"]').trigger("click");
    expect(store.resolvePromotion).toHaveBeenCalledWith("merge", CASE.id);
  });

  it("execution_failed 明确显示失败且不提供提升入口", async () => {
    const { wrapper, store } = await mountView();
    store.activeDetail = { ...DETAIL, task: { ...TASK, status: "failed" },
      report: { ...DETAIL.report!, trustState: "execution_failed" } };
    await flushPromises();

    expect(wrapper.text()).toContain("执行失败，不可沉淀");
    expect(wrapper.find('[data-action="promote-case"]').exists()).toBe(false);
  });
});
