## 1. 合同与迁移

- [x] 1.1 先编写共享 DTO、上传 policy、错误和六种 OpenAPI 操作的失败测试
- [x] 1.2 先编写 knowledge_documents migration/metadata 精确结构与 active hash 唯一性测试
- [x] 1.3 实现 TypeScript/Pydantic contracts、python-multipart 依赖与 Alembic revision

## 2. 提取与切分

- [x] 2.1 先编写 Markdown/PDF、扩展名/MIME/UTF-8/0 与 10 MiB 边界测试
- [x] 2.2 实现有界上传校验、SHA-256 和可注入 pypdf 文本提取
- [x] 2.3 先编写 fixed-character、markdown-heading、paragraph、非法参数和 preview 上限测试
- [x] 2.4 实现 ChunkingConfig、chunk_document_text 与 DocumentChunkingService

## 3. owner-scoped 文档领域

- [x] 3.1 先编写稳定默认 KB、Repository 参数、跨 owner/父子 scope 与 hash 冲突测试
- [x] 3.2 实现冻结 records、Repository Protocol、SQLite adapter 与 KnowledgeDocumentService
- [x] 3.3 先编写 overwrite/普通删除的完整向量 scope、失败不软删除与追溯测试
- [x] 3.4 实现 DocumentVectorDeleter 注入、软删除与覆盖事务语义

## 4. HTTP API

- [x] 4.1 先编写认证、六种 API、multipart、409/overwrite、preview、request-id 测试
- [x] 4.2 实现 dependencies/router、统一 envelope/error 与 app 注册
- [x] 4.3 增加 import-safety 与 FastAPI OpenAPI/manifest 跨语言合同测试

## 5. 验证与归档

- [x] 5.1 运行 `uv sync`、`uv run alembic upgrade head`、Ruff、strict Pyright 和 backend pytest
- [x] 5.2 运行 contracts typecheck/test、`openspec validate --all` 和 `git diff --check`
- [x] 5.3 使用 openspec-verify-change 核对任务、需求、场景与设计并修复全部 CRITICAL/WARNING
- [x] 5.4 同步 delta specs、归档 change，并复检无 active change 与全部格式门禁
