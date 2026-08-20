## 1. Typed client 与合同边界

- [x] 1.1 先为知识库/文档/预览/background-job 恢复、multipart 策略字段和错误 envelope 编写失败测试
- [x] 1.2 扩展 typed knowledgeClient，复用共享 contracts 与现有 ApiClient 完成真实 API 调用

## 2. Pinia knowledge store

- [x] 2.1 先为初始化、认证清理、上传后显式建任务和服务端刷新编写失败测试
- [x] 2.2 实现 knowledge store 的知识库、文档、详情、预览、任务与请求状态
- [x] 2.3 先为约 2 秒 poll、任务恢复、retry、手动重建和 timer 清理编写失败测试
- [x] 2.4 实现单调度器轮询、background-job 关联恢复、失败原因、retry 和重建
- [x] 2.5 先为 hash 冲突覆盖确认、删除确认及成功后刷新编写失败测试
- [x] 2.6 实现仅内存上传草稿、显式 overwrite/delete 确认和 owner 数据清理

## 3. 桌面知识库工作区

- [x] 3.1 先为上传策略控件、单知识库 selector 隐藏、中文状态和 `/knowledge` 真实路由编写失败组件测试
- [x] 3.2 实现 KnowledgeView、上传面板、文档列表和共享可访问交互
- [x] 3.3 先为默认折叠行内详情、真实 preview、metadata/preview 有界滚动和长表格横向滚动编写失败组件测试
- [x] 3.4 实现行内详情、状态徽标、确认对话与桌面滚动 CSS 约束，不新增移动流程

## 4. 验证与真实 smoke

- [x] 4.1 运行 frontend typecheck/test/build、contracts typecheck/test、相关 backend tests、openspec validate --all 和 git diff --check，并修复问题
- [x] 4.2 在本地桌面浏览器使用真实后端完成 MD/PDF 上传、显式索引、实际切分预览和删除 smoke，如实记录外部服务状态
- [x] 4.3 使用 openspec-verify-change 核对完整性、正确性和设计一致性，修复全部 CRITICAL 并处理 WARNING
- [x] 4.4 同步 delta specs 到主规格，重新验证后归档 change
