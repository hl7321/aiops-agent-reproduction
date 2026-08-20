## 1. 共享合同与验收基线

- [x] 1.1 先增加 contracts/backend 失败测试，覆盖 Prompt/Skill/configuration DTO、选择请求、删除结果、multipart policy 与七个 OpenAPI operation
- [x] 1.2 扩展 TypeScript contracts、manifest、Python/Pydantic 镜像和导出，确保 bearer、401/403/404/409/validation 复用且无私有 payload
- [x] 1.3 增加前后端序列化与机器可读 OpenAPI 对齐测试，使 contracts typecheck/test 和后端合同测试通过

## 2. Alembic、records 与 owner-scoped Repository

- [x] 2.1 先增加 fresh migration/metadata 失败测试，覆盖三张表、字段、owner 外键、同用户 name 唯一、configuration 单行与禁止额外 selection/catalog 表
- [x] 2.2 新增 Alembic revision、ORM model、不可变 records、Repository Protocol 与 `super_ai.memory.extended_sqlite` adapter
- [x] 2.3 先用两个用户增加 Repository 合同测试，覆盖 Prompt CRUD、Skill CRUD、稳定排序、跨 owner 不可见和 import-safety
- [x] 2.4 实现 configuration 原子选择替换、非法 id 全回滚、删除选中 Prompt 置 null、删除 Skill 自动退出选择，并使事务测试通过

## 3. SKILL.md parser 与标准示例

- [x] 3.1 在生产代码前增加 parser 失败测试，覆盖严格 filename、256 KiB、UTF-8、frontmatter object、name/description、JSON-safe metadata 与正文
- [x] 3.2 显式增加 `PyYAML>=6,<7` 并更新 uv.lock，实现 safe_load、name 规范化、summary 与安全 validation error
- [x] 3.3 增加同 owner 规范化 name 冲突 409、不同 owner 同名成功和完整 content/metadata 保存测试
- [x] 3.4 创建五个 `docs/examples/skills/<name>/SKILL.md`，用生产 parser 测试目录名/name 一致且证明新用户不会自动获得示例

## 4. Prompt/Skill configuration service 与 API

- [x] 4.1 先增加 service/API 失败测试，覆盖 GET/PUT configuration、Prompt create/update/delete、Skill multipart upload/delete 和统一 envelope/requestId
- [x] 4.2 实现 configuration service、依赖注入与 router，所有 id 操作在同一 SQL 中带 owner scope并使用确定错误语义
- [x] 4.3 测试配置 PUT 原子性、删除 fallback、重复上传、非法 multipart、401 与两个用户跨租户隔离
- [x] 4.4 更新 app/router registration 与 OpenAPI 测试，证明模块 import/openapi 加载不读配置、不连接 SQLite/LLM/Milvus

## 5. Progressive system prompt 与 load_skill Tool

- [x] 5.1 先增加配置快照与 assembler 失败测试，使用正文 sentinel 证明 system prompt 只有平台规则、当前 Prompt 和选中 Skill name/description
- [x] 5.2 实现 frozen request snapshot、独立短事务 loader 与信任分层 SystemPromptAssembler；无选择时仍保留平台安全规则
- [x] 5.3 先增加 `load_skill` Tool 失败测试，覆盖已选按需正文、name 规范化、未选中/删除/跨 owner 拒绝和未调用时零正文读取
- [x] 5.4 实现 owner+本轮 allowlist 双重约束的请求级 `load_skill` Tool，并接入现有工具审计与安全错误流
- [x] 5.5 修改 Agent factory/runner 接受动态 system prompt，测试模型自主调用/不调用 load_skill、配置跨轮更新、用户 Prompt 不扩大权限与 reasoning 不合成

## 6. 前端 typed configuration client/store

- [x] 6.1 先增加 configuration client 失败测试，覆盖七个 operation、bearer/envelope、共享 DTO 与 Skill FormData 原样上传
- [x] 6.2 实现 typed configuration client，并禁止复制 Prompt/Skill/configuration 私有 payload
- [x] 6.3 先增加 Pinia store 失败测试，覆盖初始化、选择更新、Prompt CRUD、Skill upload/delete、服务端对账、401/logout 清理和无 localStorage 领域写入
- [x] 6.4 实现 protected configuration store；只提供 P19 可消费的状态/actions，不新增最终侧栏或静态 mock catalog

## 7. 验证、真实 smoke 与归档

- [x] 7.1 运行 `uv sync`、`uv run alembic upgrade head`、backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 7.2 运行 contracts typecheck/test、frontend typecheck/test/build/secret scan、`openspec validate --all` 与 `git diff --check`
- [x] 7.3 在 ignored 本机 Qwen 凭据可用时执行一次真实模型按摘要调用 `load_skill` smoke；不可用时明确记录未执行，不把 fake 测试称为真实连通
- [x] 7.4 使用 `$openspec-verify-change` 检查完整性、正确性与设计一致性，修复全部 CRITICAL 并处理 WARNING 后重跑受影响门禁
- [x] 7.5 将全部 delta specs 智能同步到主规格，确认任务与验证证据完整，再使用 `$openspec-archive-change` 归档
