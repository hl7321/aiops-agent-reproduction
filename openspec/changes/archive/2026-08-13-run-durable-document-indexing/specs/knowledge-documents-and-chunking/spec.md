## MODIFIED Requirements

### Requirement: 文档事实记录可追溯且不依赖 MinIO
文档 SHALL 保存 owner、knowledge base、原始文件名、size、MIME、SHA-256、uploadedAt、`pending|running|succeeded|failed|cancelled` index status、实际 chunking 策略/参数、可索引正文和软删除时间。应用 MUST NOT 把原始文档写入 MinIO；API DTO MUST NOT 返回完整可索引正文。上传成功只创建文档，MUST NOT 自动创建 background job；在客户端显式创建首次 index task 前，文档状态为 pending。

#### Scenario: 查询文档详情
- **WHEN** owner 获取已保存文档
- **THEN** DTO 返回可审计元数据、五种之一的 index status 与实际 chunking config，但不返回完整正文

#### Scenario: 上传与索引调度分离
- **WHEN** owner 成功上传文档但客户端尚未创建 index task
- **THEN** 文档为 pending，且没有 background job 或进程内 asyncio task 被创建

### Requirement: 预览与后续索引复用同一切分入口
preview 与 durable indexing SHALL 调用同一个 `chunk_document_text` 领域入口或其同一 service 封装。每个 chunk MUST 含稳定顺序、策略和可追溯 metadata；preview 最多返回前 12 段，每段 excerpt 最多 400 字，并使用文档保存的实际策略与参数。

#### Scenario: 有界预览
- **WHEN** 文档切分结果超过 12 段或单段超过 400 字
- **THEN** preview 仅返回前 12 段且每段 excerpt 不超过 400 字，同时返回总 chunk 数

#### Scenario: 预览结果可被索引复现
- **WHEN** 对同一正文和保存配置分别执行 preview 与 durable indexing 切分
- **THEN** 两者的 chunk 顺序、正文边界和追溯 metadata 一致
