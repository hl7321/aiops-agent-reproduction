## 1. 配置与共享合同

- [x] 1.1 先增加配置失败测试，覆盖两类 source、重复名称、URL/timeout/Basic Auth 边界和模板空凭据，再实现 typed alert/CLS settings 与新模板结构。
- [x] 1.2 先增加 contracts 失败测试，覆盖 ActiveAlert DTO、`SYSTEM_ALERT_SOURCES_UNAVAILABLE` 和认证 OpenAPI path，再同步 TypeScript、manifest 与 Pydantic 合同。

## 2. 告警 Provider 与聚合

- [x] 2.1 先增加 Prometheus payload 的失败测试，再实现 `/api/v1/alerts` 请求、字段/状态/时间标准化和安全错误。
- [x] 2.2 先增加 Alertmanager payload 的失败测试，再实现 `/api/v2/alerts` 请求、active/suppressed/unprocessed 映射与 rawContext 保留。
- [x] 2.3 先增加并发、单源失败、空成功源、全失败和稳定排序测试，再实现 AlertProvider Protocol、request-scoped factory 与 Aggregator。

## 3. 认证活跃告警 API

- [x] 3.1 先增加未认证不访问 source、认证成功、部分失败和全失败 envelope 测试，再实现依赖与 `GET /aiops/alerts/active`。
- [x] 3.2 将 alert settings 注入 `create_app/create_configured_app`，增加配置化 app 与 import/普通启动无网络副作用测试。

## 4. 独立 CLS 日志工具

- [x] 4.1 用 PEP 723 与独立 lock 隔离锁定 `tencentcloud-cls-sdk-python==1.0.4`，保持 backend 依赖图不变；先增加脚本 import、配置、HTTPS endpoint 与 count 1..100 失败测试。
- [x] 4.2 先增加三条安全日志的字段/有界/无凭据测试，再实现确定性结构化记录与 protobuf LogGroupList 构造。
- [x] 4.3 先增加 endpoint 路由、`put_log_raw(topicId, groups)`、logsetId 不参与调用、单次上传和异常脱敏测试，再实现延迟 SDK factory 与显式 CLI main。
- [x] 4.4 更新 `scripts/README.md`，明确本地 JSON 配置、人工确认目标、真实写入副作用和禁止环境变量/自动上传。

## 5. 验证与归档准备

- [x] 5.1 运行 backend pytest、Ruff、strict Pyright 与 contracts typecheck/test，修复全部问题。
- [x] 5.2 运行 `openspec validate --all` 与 `git diff --check`；只在用户确认目标后执行真实 CLS smoke，未确认时明确记录未执行。
- [x] 5.3 使用 `$openspec-verify-change` 核对完整性、正确性和设计一致性，修复所有 CRITICAL/WARNING 并重新运行受影响门禁。

归档动作：验证通过后同步 delta specs，并使用 `$openspec-archive-change` 归档本 change；该生命周期动作不作为归档前任务复选框。
