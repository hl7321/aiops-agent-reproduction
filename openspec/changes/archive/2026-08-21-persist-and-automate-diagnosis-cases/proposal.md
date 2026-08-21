## Why

P21 已能生成有证据来源的成功诊断报告，但历史故障尚不会稳定进入知识循环。现在需要把成功诊断自动沉淀为可检索、可索引且 owner-scoped 的结构化 case，同时保留显式手动补充路径。

## What Changes

- 新增结构化 `aiops_diagnostic_cases` 持久化、owner-scoped 列表与详情 API。
- 成功 report 完成后，由独立自动持久器幂等创建 case、诊断 Markdown 文档和 durable index task。
- 保留 `POST /aiops/diagnostics/{id}:save-to-knowledge` legacy 手动路径；它只创建文档与索引任务，不创建 case。
- case 文档使用 `knowledgeType=diagnostic-case` 和 source diagnosis/report/evidence metadata，参与后续混合检索。
- 失败、取消或没有最终成功 report 的诊断不创建自动 case。

## Capabilities

### New Capabilities

- `diagnosis-case-persistence`: 结构化诊断 case、自动/手动知识沉淀、索引调度、幂等与 owner scope。

### Modified Capabilities

- `aiops-diagnosis-and-evidence`: 成功 report 节点完成后触发自动 case 持久化。
- `api-and-sse-contracts`: 登记 case DTO、列表/详情与手动保存操作。

## Impact

影响 Alembic、AIOps report runtime、知识文档与索引服务组合边界、共享 TypeScript/Pydantic contracts、OpenAPI manifest 和后端测试；不新增向量直写、前端页面或外部依赖。
