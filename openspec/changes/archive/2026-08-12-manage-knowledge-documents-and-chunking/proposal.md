## Why

后续知识索引与检索需要先有安全、可追溯且可重复切分的文档事实来源。当前项目只有 tenant-safe SQLite/Milvus 边界，没有默认知识库、文档上传政策或统一 splitter，容易让预览与索引产生不同 chunk。

## What Changes

- 为每个已认证用户提供一个稳定、隐式创建且不可跨 owner 访问的默认知识库；当前不提供多知识库创建或删除。
- 增加 owner-scoped 文档上传、列表、详情、删除和 chunk preview API。
- 只接收不超过 10 MiB 的 UTF-8 Markdown 与 PDF，由后端权威校验文件扩展名、MIME、大小并用 pypdf 提取 PDF 文本。
- 使用 Alembic 保存文档元数据、SHA-256、可索引正文、软删除状态、索引状态与实际 chunking 配置；不把原文写入 MinIO。
- 相同 owner/知识库/hash 默认返回稳定 409；显式 overwrite 软删除旧文档并通过完整 tenant/KB/document scope 清理旧向量，普通删除同样清理。
- 提供 fixed-character、markdown-heading、paragraph 三种切分策略及同一 `chunk_document_text` 入口；preview 最多 12 段且 excerpt 最多 400 字。
- 扩展共享 contracts、错误目录、multipart policy 常量与机器可读 OpenAPI path。
- 不实现 embedding、索引 worker、完整检索链路或知识库前端 UI。

## Capabilities

### New Capabilities

- `knowledge-documents-and-chunking`：默认知识库、文档存储/提取/覆盖删除、统一切分与安全预览能力。

### Modified Capabilities

- `api-and-sse-contracts`：增加知识库与文档 DTO、上传 policy、业务错误和六个受保护 OpenAPI path。

## Impact

- 后端新增 knowledge 领域、SQLite adapter、Alembic migration、multipart API 与可注入向量删除端口。
- `packages/api-contracts` 新增知识文档类型、上传 policy 常量及 path manifest。
- 后端新增 `python-multipart` 运行依赖；复用现有 pypdf、langchain-text-splitters 和 Milvus adapter 边界。
- 自动化测试只使用临时 SQLite、内存上传和 fake vector deleter，不读取真实配置或凭据。
