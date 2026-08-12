export * from "./auth";
export * from "./background-jobs";
export * from "./errors";
export * from "./http";
export * from "./knowledge";
export * from "./openapi";
export * from "./sse";

/** foundation 健康检查的共享成功数据。 */
export interface FoundationStatus {
  status: "ok";
}
