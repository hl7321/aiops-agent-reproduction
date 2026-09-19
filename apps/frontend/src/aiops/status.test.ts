import { describe, expect, it } from "vitest";

import { diagnosticStatusLabel, INSUFFICIENT_EVIDENCE_CODE } from "./status";

describe("AIOps 诊断终态文案", () => {
  it("证据不足的诊断不显示为成功", () => {
    const label = diagnosticStatusLabel({
      status: "failed",
      failureCode: INSUFFICIENT_EVIDENCE_CODE,
    });

    expect(label).toBe("证据不足");
    expect(label).not.toBe("已成功");
  });

  it("系统故障与证据不足给出不同措辞", () => {
    expect(diagnosticStatusLabel({ status: "failed", failureCode: "SYSTEM_UNAVAILABLE" }))
      .toBe("失败");
    expect(diagnosticStatusLabel({ status: "failed", failureCode: null })).toBe("失败");
  });

  it("可信报告仍然显示为成功", () => {
    expect(diagnosticStatusLabel({ status: "succeeded", failureCode: null })).toBe("已成功");
  });

  it("未选择任务时给出占位文案", () => {
    expect(diagnosticStatusLabel(null)).toBe("未选择");
  });
});
