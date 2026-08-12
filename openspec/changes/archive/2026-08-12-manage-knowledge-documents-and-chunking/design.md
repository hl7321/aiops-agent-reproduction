## Context

参见 [proposal.md](./proposal.md)。项目已有认证 CurrentUser/OwnerScope、Alembic/SQLite Repository、统一 contracts 及 tenant-safe Milvus `delete_document`，但没有 knowledge 领域。模块 import 不得打开 SQLite/Milvus；领域服务不得接收 ORM model 或 AsyncSession。

## Goals / Non-Goals

**Goals:**

- 建立单一默认知识库、规范化文档表、owner-scoped Repository 和统一切分服务。
- 让上传校验、PDF/Markdown 提取、重复覆盖与向量清理可以通过依赖注入单元测试。
- 让预览与未来索引复用相同纯函数并保留 chunk metadata。
- 先定义 TypeScript/manifest 合同，再实现 Pydantic 与 FastAPI 路由。

**Non-Goals:**

- 不实现 embedding、Milvus insert/search、后台索引 handler、RAG 或完整知识 UI。
- 不提供自定义知识库创建/删除，也不保存上传原始二进制。
- 不读取真实 vectorStore 配置；API 测试注入 fake vector deleter。

## Decisions

### 1. 默认知识库 id 确定性派生且不单独建表

默认知识库 id 使用固定 namespace 对 `user_id` 做 UUID5 派生，因而跨进程稳定且不同用户不同。知识库是当前逻辑资源，不新增可变 knowledge_bases 表；文档表仍保存 `knowledge_base_id` 并由 service 验证其等于当前用户派生值。

相比启动时插入默认行，此方案不产生 race 或额外事务；未来引入多知识库时可迁移为显式表，但本 change 不提前建模。

### 2. 单一 documents 表保存可索引事实

Alembic 新增 `knowledge_documents`，规范化保存 owner、KB、文件元数据、hash、正文、index_status、chunking_strategy、max/overlap、uploaded/deleted 时间。活动重复由查询与事务内冲突检查保证；SQLite 局部唯一索引约束 `(owner_user_id, knowledge_base_id, sha256)` 在 `deleted_at IS NULL` 时唯一。

正文是未来 indexing 的事实来源；不保存原始二进制且不使用 MinIO。DTO 不暴露正文，避免意外大响应。

### 3. 上传先读取有界字节再权威校验

FastAPI 使用 multipart `file`、JSON 字符串 `chunkingConfig` 与布尔 `overwrite`。读取最多 `10 MiB + 1` 以检测超限；扩展名和 MIME 必须配对。Markdown 严格 UTF-8；PDF 通过注入的 extractor（默认 pypdf）从 BytesIO 逐页提取，解析失败或空文本返回安全错误。

增加 `python-multipart` 是 FastAPI 解析 multipart 的必要依赖。测试使用内存文件，不创建开发者本机配置。

### 4. splitter 是纯领域入口

`chunk_document_text(text, config)` 返回有序冻结 chunk record。fixed-character 使用 `RecursiveCharacterTextSplitter` 的字符长度函数和指定 overlap；markdown-heading 按 ATX 标题边界保留标题路径 metadata；paragraph 按一个或多个空行归一分段。空 chunk 被过滤。

`DocumentChunkingService` 只封装该入口并裁剪 preview；未来 indexing 必须调用同一入口。chunk metadata 至少包含 index、strategy，并为 Markdown 标题保留 heading path。

### 5. 覆盖与删除采用向量端口 + SQLite 事务边界

领域服务依赖 `DocumentVectorDeleter` Protocol，调用必须传 OwnerScope、KB、document。overwrite 找到所有同 hash 活动旧文档，逐个删除向量成功后在同一 SQLite 事务软删除，再创建新记录。普通删除同理。

外部 Milvus 与 SQLite 无法原子提交：选择“先删向量、后软删除”。向量删除应为幂等；失败时 SQLite 不变，避免数据库声称已删除但旧向量仍可召回。测试使用 fake deleter，不连接真实 Milvus。

### 6. 父知识库错误与文档错误分层

service 在任何文档 Repository 调用前仅用确定性 id 验证当前用户 KB：不匹配直接 `AUTH_FORBIDDEN`，无需无 scope 数据探测。文档 Repository 的 list/get/delete/duplicate 查询均以 owner_user_id 为首个业务参数，并在同一 SQL 中包含 KB/document。

## Risks / Trade-offs

- [PDF 仅包含扫描图片时无文本] → 返回安全的不可索引错误；OCR 留给后续提案。
- [10 MiB 文件一次读入内存] → 当前桌面本地范围可接受，并以 `limit + 1` 严格限界；不保存原始二进制。
- [向量删除成功而 SQLite 提交失败] → 删除是幂等且未来可重新索引；优先防止已软删除文档残留可召回向量。
- [UUID5 默认 KB 未来迁移] → namespace 与算法写入合同测试，未来显式表沿用现有 id。
- [Markdown 标题语法覆盖有限] → 当前支持常用 ATX `#` 标题，Setext/复杂 AST 留给未来且不影响统一入口。

## Migration Plan

1. 安装 multipart 依赖并升级 Alembic 到 `20260812_0004`。
2. 新表为空，无既有文档迁移；API 首次读取即可派生默认知识库。
3. 部署后不自动连接 Milvus；生产组装显式注入已配置 adapter，测试使用 fake。
4. 回滚前停止应用，migration downgrade 删除新表；没有 MinIO 对象需要清理。
