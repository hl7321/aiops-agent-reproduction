# knowledge-documents-and-chunking Specification

## Purpose
本能力为每个用户提供单一、稳定且 owner 隔离的默认知识库，并以统一上传政策、文档事实记录和切分入口支撑可预览、可追溯且可安全清理的后续索引流程。
## Requirements
### Requirement: 每个用户拥有稳定的隐式默认知识库
系统 SHALL 为每个已认证用户返回且仅返回一个稳定知识库；同一用户跨请求获得相同知识库 id，不同用户不得读取或使用彼此知识库。当前范围 MUST NOT 提供创建或删除多个知识库的接口。

#### Scenario: 重复获取默认知识库
- **WHEN** 同一用户多次调用 `GET /knowledge-bases`
- **THEN** 每次只返回同一个 owner-scoped 默认知识库

#### Scenario: 使用其他用户知识库
- **WHEN** 用户 B 把用户 A 的知识库 id 用于文档操作
- **THEN** 系统返回 `AUTH_FORBIDDEN` 403 且不探测或返回 A 的文档

### Requirement: 上传政策由后端权威执行
系统 SHALL 只接受扩展名与 MIME 同时匹配的 UTF-8 `.md`（`text/markdown`）或 `.pdf`（`application/pdf`）文件，文件大小 MUST 大于零且不超过 10 MiB。Markdown MUST 严格按 UTF-8 解码；PDF MUST 使用 pypdf 提取非空可索引文本。任何政策失败 MUST 在持久化前使用共享 validation/business 错误响应。

#### Scenario: 上传合法 Markdown
- **WHEN** 用户上传不超过限制、MIME 正确且为 UTF-8 的 `.md`
- **THEN** 系统保存规范化可索引正文和文件元数据

#### Scenario: 上传合法 PDF
- **WHEN** 用户上传不超过限制且 MIME 正确的 `.pdf`
- **THEN** 系统提取各页文本并保存为可索引正文

#### Scenario: 拒绝格式、MIME、编码或大小异常
- **WHEN** 扩展名/MIME 不匹配、Markdown 不是 UTF-8、PDF 无法解析、文件为空或超过 10 MiB
- **THEN** 系统拒绝上传且不新增文档记录

### Requirement: 文档事实记录可追溯且不依赖 MinIO
文档 SHALL 保存 owner、knowledge base、原始文件名、size、MIME、SHA-256、uploadedAt、index status、实际 chunking 策略/参数、可索引正文和软删除时间。应用 MUST NOT 把原始文档写入 MinIO；API DTO MUST NOT 返回完整可索引正文。

#### Scenario: 查询文档详情
- **WHEN** owner 获取已保存文档
- **THEN** DTO 返回可审计元数据与实际 chunking config，但不返回完整正文

### Requirement: 重复 hash 与显式覆盖具有确定语义
相同 owner 与知识库中存在相同 SHA-256 的未删除文档时，默认上传 MUST 返回 `BUSINESS_CONFLICT` 409。只有 multipart 明确设置 `overwrite=true` 才可软删除全部冲突旧文档、按 owner/tenant + knowledgeBaseId + documentId 清理各自旧向量，再保存新文档；新旧记录 MUST 可追溯。

#### Scenario: 默认拒绝重复内容
- **WHEN** 用户向同一默认知识库再次上传相同字节且未声明 overwrite
- **THEN** 返回 `BUSINESS_CONFLICT`，旧文档保持未删除且不调用向量删除

#### Scenario: 显式覆盖重复内容
- **WHEN** 用户以 `overwrite=true` 上传相同字节
- **THEN** 冲突旧文档被 owner-scoped 软删除、旧向量使用完整 scope 清理，随后创建新的活动文档

### Requirement: 文档读取与删除强制父子 owner scope
列表、详情、删除与 preview MUST 在同一 Repository 查询中同时约束 `owner_user_id + knowledge_base_id + document_id`。知识库不可见统一返回 `AUTH_FORBIDDEN`；直接文档不存在或跨 owner 统一返回不可枚举 404。普通删除 MUST 先以完整 tenant/KB/document scope 清理向量，再软删除文档。

#### Scenario: 两个用户读取或删除同名文档
- **WHEN** 用户 B 使用用户 A 的 KB/document 标识查询、预览或删除
- **THEN** B 无法获得或修改 A 的记录，且不会执行无 tenant 的向量删除

#### Scenario: owner 删除文档
- **WHEN** owner 删除活动文档
- **THEN** 系统使用 tenantId + knowledgeBaseId + documentId 清理向量并软删除该文档

### Requirement: 三种切分策略参数明确
系统 SHALL 支持 `fixed-character`、`markdown-heading` 与 `paragraph`。默认策略 MUST 为 `fixed-character`，默认 `maxCharacters=1200`、`overlap=200`；只有 fixed-character 接受 maxCharacters/overlap，且 MUST 满足 `maxCharacters > 0`、`overlap >= 0`、`overlap < maxCharacters`。其他策略收到这两个参数时 MUST 拒绝。

#### Scenario: fixed-character 使用默认值与重叠
- **WHEN** 未传策略参数或显式选择合法 fixed-character 配置
- **THEN** 系统按实际 max/overlap 切分并保存规范化配置

#### Scenario: Markdown 标题与段落切分
- **WHEN** 选择 markdown-heading 或 paragraph
- **THEN** 系统按标题层级或空行段落产生有序、非空 chunk，且配置不包含 fixed 专用参数

#### Scenario: 拒绝非法切分参数
- **WHEN** overlap 不小于 max、数值越界，或非 fixed 策略携带 max/overlap
- **THEN** 系统返回字段可定位的 validation 错误

### Requirement: 预览与后续索引复用同一切分入口
preview 与后续 indexing SHALL 调用同一个 `chunk_document_text` 领域入口或其同一 service 封装。每个 chunk MUST 含稳定顺序、策略和可追溯 metadata；preview 最多返回前 12 段，每段 excerpt 最多 400 字，并使用文档保存的实际策略与参数。

#### Scenario: 有界预览
- **WHEN** 文档切分结果超过 12 段或单段超过 400 字
- **THEN** preview 仅返回前 12 段且每段 excerpt 不超过 400 字，同时返回总 chunk 数

#### Scenario: 预览结果可被索引复现
- **WHEN** 对同一正文和保存配置分别执行 preview 与后续 indexing 切分
- **THEN** 两者的 chunk 顺序、正文边界和追溯 metadata 一致

### Requirement: 知识文档 API 使用共享合同
系统 SHALL 提供 `GET /knowledge-bases`、`GET/POST /knowledge-bases/{kb}/documents`、`GET/DELETE /knowledge-bases/{kb}/documents/{document}` 与 `GET /knowledge-bases/{kb}/documents/{document}/chunk-preview`。全部 path MUST 使用 bearer、统一 envelope/requestId 以及共享 401/403/404/409/validation 合同。

#### Scenario: 已认证用户管理默认知识库文档
- **WHEN** owner 通过六个 path 上传、列表、读取、预览或删除文档
- **THEN** 响应使用共享 KnowledgeBase/Document/ChunkPreview DTO 和统一 envelope

#### Scenario: 未认证访问知识 API
- **WHEN** 请求没有有效 bearer token
- **THEN** 返回共享 `AUTH_REQUIRED` 401
