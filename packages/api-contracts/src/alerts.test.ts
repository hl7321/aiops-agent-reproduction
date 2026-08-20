import { describe, expect, expectTypeOf, it } from "vitest";

import { ALERT_OPENAPI_OPERATIONS, ERROR_DEFINITIONS } from "./index";
import type { ActiveAlert, ActiveAlertsData, AlertSource } from "./index";

describe("活跃告警共享合同", () => {
  it("定义包含 source status 和 rawContext 的标准告警", () => {
    expectTypeOf<AlertSource["type"]>().toEqualTypeOf<
      "prometheus-v1" | "alertmanager-v2"
    >();
    expectTypeOf<ActiveAlert["status"]>().toEqualTypeOf<
      "pending" | "firing" | "suppressed" | "unprocessed"
    >();
    expectTypeOf<ActiveAlert["service"]>().toEqualTypeOf<string | null>();
    expectTypeOf<ActiveAlert["severity"]>().toEqualTypeOf<string | null>();
    expectTypeOf<ActiveAlert>().toHaveProperty("rawContext");
    expectTypeOf<ActiveAlertsData["items"]>().toEqualTypeOf<readonly ActiveAlert[]>();
  });

  it("登记唯一 bearer-protected 活跃告警 operation", () => {
    expect(ALERT_OPENAPI_OPERATIONS).toEqual([
      {
        path: "/aiops/alerts/active",
        method: "GET",
        operationId: "getActiveAlerts",
        successData: "ActiveAlertsData",
        security: ["BearerAuth"],
        errors: [
          "AUTH_REQUIRED",
          "AUTH_FORBIDDEN",
          "SYSTEM_ALERT_SOURCES_UNAVAILABLE",
        ],
      },
    ]);
  });

  it("公开安全的全源不可用错误", () => {
    expect(ERROR_DEFINITIONS.SYSTEM_ALERT_SOURCES_UNAVAILABLE).toEqual({
      code: "SYSTEM_ALERT_SOURCES_UNAVAILABLE",
      category: "system",
      httpStatus: 503,
      defaultMessage: "活跃告警来源暂时不可用",
    });
  });
});
