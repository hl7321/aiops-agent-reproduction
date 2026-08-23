## 1. 合同与迁移验收测试

- [x] 1.1 先为 attempt/errorCategory、report trustState、显式提升结果与重复候选编写 contracts/OpenAPI 失败测试
- [x] 1.2 先为报告可信字段、case fingerprint/source provenance 和并发唯一约束编写 Alembic fresh-upgrade/metadata 失败测试
- [x] 1.3 增加 Alembic migration 与 ORM/record/Repository 合同，保证所有新查询和写入 owner scoped
- [x] 1.4 更新 TypeScript/Pydantic contracts、OpenAPI path/error 目录和后端序列化，使合同与迁移测试通过

## 2. AIOps 双层工具白名单

- [x] 2.1 先编写动态发现工具与 AIOps policy 取交集、未登记/非只读工具拒绝、恢复时工具消失的失败测试
- [x] 2.2 实现 request-scoped AIOps tool policy/capability catalog，保留现有 owner MCP 动态发现和重名保护
- [x] 2.3 更新 Planner 输入为有界名称/描述/Schema/条件依赖 catalog，并编写单 SearchLog、可信 Query 跳过 builder、未验证 Query 要求 builder、时序 claim 条件要求 context 和未知工具测试
- [x] 2.4 实现最多三次 Planner 校验纠错，向模型传递脱敏结构化错误而不是重复相同 Prompt

## 3. 核心 CLS Schema adapter

- [x] 3.1 先用官方工具 Schema 和脱敏真实响应样本编写核心 CLS 三工具输入/输出失败测试，并为 QueryMetric 等其他允许工具编写独立验证/adapter 合同测试
- [x] 3.2 实现所有 policy 工具的 runtime 输入验证和安全产物 adapter；核心 CLS 三工具使用显式 Pydantic model，并统一解包 MCP content/structured content
- [x] 3.3 保留本地 JSON `clsLogUpload.region/topicId`，测试缺失时报配置错误，并禁止模型/客户端覆盖权威值
- [x] 3.4 实现 SearchLog 原始命中选择，以及仅在条件成立时把 Region/TopicId/Time/PkgId/PkgLogId 确定性装配到 DescribeLogContext
- [x] 3.5 用显式 adapter evidence kind 替换工具名字符串推断，持久化 query artifact、log hit、log context、metric 与 knowledge 关联

## 4. Executor、重试与可信报告门禁

- [x] 4.1 先编写 Pydantic validation、模型可修正输入、空结果 query refinement、timeout/429/5xx 退避、401/403/配置/越权/Schema 不兼容不重试、checkpoint/restart 和审计脱敏测试
- [x] 4.2 扩展 step/audit/event/checkpoint 的 attempt 与错误分类，实现独立 retry classifier 和最多三次的调用/纠错
- [x] 4.3 先编写 SearchLog 必需、时序 claim 的 context 条件门禁、非时序 claim 可由其他独立证据满足、Replanner 不得伪造工具成功的测试
- [x] 4.4 实现 Profile/claim evidence evaluator；Replanner 可选择其他已登记证据工具，但只有 evaluator 通过才能产生 verified_evidence
- [x] 4.5 实现 verified_evidence/insufficient_evidence/execution_failed，模型失败说明不可把任务转成可信 succeeded
- [x] 4.6 删除 report 节点对 DiagnosisCasePersistor 的自动调用，并验证报告保存、SSE terminal 和 durable retry 一致

## 5. 人工认可与 canonical case 去重

- [x] 5.1 先编写 positive/negative/删除反馈审批、显式提升、跨 owner 和客户端伪造认可的失败测试
- [x] 5.2 实现 owner-scoped report promotion API/service，在写入前重新验证 report、trustState、uncertainty、links 和最新反馈
- [x] 5.3 先编写同 report 幂等、跨 task exact duplicate、并发唯一、semantic similar 待人工选择的失败测试
- [x] 5.4 实现版本化 incident/knowledge fingerprint、canonical case 和 diagnostic_case_sources provenance
- [x] 5.5 保证 exact duplicate 只追加 source，semantic similar 不写 document/vector，批准的新 case 只经知识文档与 durable indexing 边界
- [x] 5.6 收紧 legacy save-to-knowledge，禁止其绕过可信报告和人工认可门禁

## 6. 十套 CLS 上下文 fixture

- [x] 6.1 先编写 java-ecommerce 每 incident 多行有序日志、稳定隔离 context flow、数量/关联/安全扫描和 import 无副作用失败测试
- [x] 6.2 扩展既有 generate_and_upload_cls_logs.py，保持 quant profile/count 兼容并生成十套可查询上下文 payload
- [x] 6.3 更新真实 smoke 指南，明确只在用户确认后验证 SearchLog 非空 Time/PkgId/PkgLogId 与 DescribeLogContext 链路

## 7. 前端 AIOps 可信交互

- [x] 7.1 先编写 store/client/component 失败测试，覆盖 attempt、校验分类、execution_failed、insufficient_evidence、条件上下文、trustState、反馈审批、提升和相似候选
- [x] 7.2 更新 typed aiopsClient/Pinia store，消费真实合同且不保存 raw MCP JSON、权威配置或完整工具参数
- [x] 7.3 更新 timeline/report/case UI，展示重试与证据门禁，并只允许符合条件的报告显式提升
- [x] 7.4 实现 exact duplicate 打开 canonical case、semantic similar 人工选择和失败保留可重试输入

## 8. 验证、规格同步与归档

- [x] 8.1 运行 migration、受影响 backend pytest、Ruff、strict Pyright，并修复全部问题
- [x] 8.2 运行 contracts typecheck/test、frontend typecheck/test/build 和脚本语法/fixture 测试
- [x] 8.3 运行 `openspec validate --all`、`docker compose -f infra/compose.yaml config`、WIKI active/include/count/docs build 和 `git diff --check`
- [x] 8.4 使用 openspec-verify-change 核对完整性、正确性与设计一致性，修复所有 CRITICAL/WARNING 后重新运行门禁
- [x] 8.5 有用户明确授权且真实环境可用时分别执行可信 Query→SearchLog、自然语言→query-builder→SearchLog 和需要上下文的 SearchLog→DescribeLogContext smoke，再验证可信报告→认可→case→索引→再检索；否则明确记录未执行
- [x] 8.6 同步 delta specs、归档 P28、运行 wiki-sync archive 与归档后审计，并使用 Conventional Commit 提交保存
