## 1. 合同单一事实来源

- [x] 1.1 先扩展 contracts 测试，覆盖四类 envelope、错误目录、OpenAPI `/health` path、八种 SSE type、tool lifecycle 与 SSE error 复用
- [x] 1.2 运行 contracts 测试确认因合同缺失而失败
- [x] 1.3 实现机器可读 manifest、HTTP/错误/OpenAPI/SSE typed 模块和统一 entrypoint
- [x] 1.4 运行 contracts typecheck/test 并修复至通过

## 2. FastAPI 合同镜像与请求边界

- [x] 2.1 先编写后端测试，覆盖成功、已知业务错误、验证错误、系统错误、字段路径、request ID 透传/生成和 OpenAPI 对齐
- [x] 2.2 运行后端目标测试确认因统一 helper、handler 与模型缺失而失败
- [x] 2.3 实现 Pydantic 合同模型、稳定错误目录镜像、success/error helper 与安全应用错误
- [x] 2.4 实现 request ID 中间件、validation/exception handler，并迁移 `/health` 到共享成功 envelope
- [x] 2.5 增加 Python SSE 序列化模型与 manifest 对齐测试，覆盖完整事件目录、tool lifecycle 和错误结构复用
- [x] 2.6 运行 backend pytest、Ruff、strict Pyright 并修复至通过

## 3. 前端 typed transport

- [x] 3.1 先编写 apiClient 测试，覆盖 envelope 解包、typed error、bearer/request ID 注入扩展点
- [x] 3.2 先编写 SSE parser/client 测试，覆盖跨 chunk frame、单 chunk 多 frame、CRLF、tool/error 事件与共享 union
- [x] 3.3 运行前端目标测试确认因 transport 缺失而失败
- [x] 3.4 实现 typed apiClient、ApiClientError 与 header 注入扩展点
- [x] 3.5 实现增量 SSE frame parser 和 typed sseClient，所有事件类型只从 contracts entrypoint 导入
- [x] 3.6 运行 frontend typecheck/test/build 并修复至通过

## 4. 跨语言治理与文档

- [x] 4.1 先增加仓库策略测试，约束合同 entrypoint、后端序列化形状、OpenAPI 路由和前后端禁止临时 envelope/私有事件目录
- [x] 4.2 运行仓库策略测试确认新治理约束能够失败，再实现最小允许清单和对齐代码
- [x] 4.3 更新 contracts/backend/frontend README，只说明已实现合同基础、扩展顺序和验证方式

## 5. 完整验证与归档准备

- [x] 5.1 运行 contracts typecheck/test、backend pytest/Ruff/Pyright、frontend typecheck/test/build、secret 扫描与 docs build
- [x] 5.2 运行 `openspec validate --all` 和 `git diff --check`
- [x] 5.3 使用 `openspec-verify-change` 检查完整性、正确性和设计一致性，修复所有 CRITICAL 并处理 WARNING 后重新运行受影响门禁
- [x] 5.4 评估 `api-and-sse-contracts` 与 `monorepo-foundation` delta specs 的待同步差异，并确认具备 sync/archive 前置条件
