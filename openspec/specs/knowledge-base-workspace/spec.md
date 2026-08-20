# 知识库工作区规格

## Purpose

本能力定义由真实后端合同驱动的中文桌面知识库工作区，使用户能够安全完成文档上传、切分预览、持久索引跟踪、失败恢复、覆盖与删除闭环。

## Requirements

### Requirement: knowledge store 以服务器为唯一事实来源
系统 SHALL 使用 typed client 和受保护 Pinia store 管理知识库、文档、选中详情、切分预览、索引任务与覆盖确认。领域数据 MUST 来自真实受保护 API，MUST NOT 使用 localStorage、静态数组或客户端伪造结果；认证失效或 logout MUST 清空 knowledge store。

#### Scenario: 初始化知识库工作区
- **WHEN** 已认证用户进入 `/knowledge`
- **THEN** 系统携带 bearer 与 request-id 扩展点读取服务端知识库、文档和可恢复的索引任务状态

#### Scenario: 认证状态被清理
- **WHEN** API 返回 401 或用户 logout
- **THEN** knowledge store 清除知识库、文档、详情、预览、任务、确认框和轮询 timer，且不调用领域删除 API

### Requirement: 上传遵守共享文件和切分策略
上传控件 MUST 只接受共享 policy 声明的 UTF-8 Markdown 与 PDF，并在提交前提示不支持的扩展名、MIME 或超过 10 MiB 的文件；后端仍 MUST 作为权威校验者。用户 MUST 在上传前选择切分策略；`fixed-character` MUST 发送 `maxCharacters` 与 `overlap`，`markdown-heading` 和 `paragraph` MUST NOT 发送这两个字段。单知识库时 MUST 隐藏无意义的 selector。

#### Scenario: fixed-character 上传
- **WHEN** 用户选择合法 `.md` 或 `.pdf`、选择 `fixed-character` 并填写合法长度与 overlap
- **THEN** 客户端以 multipart 上传文件、完整 fixed-character 配置和 `overwrite=false`

#### Scenario: 非固定长度策略上传
- **WHEN** 用户选择 `markdown-heading` 或 `paragraph`
- **THEN** multipart 中的 chunkingConfig 只包含 strategy，不包含 maxCharacters 或 overlap

#### Scenario: 客户端即时拒绝不合规文件
- **WHEN** 文件类型或大小违反共享上传 policy，或 fixed-character 参数不满足 `overlap < maxCharacters`
- **THEN** 页面显示中文可访问错误且不发送上传请求

### Requirement: 上传后显式创建并跟踪持久索引任务
文档上传成功后客户端 MUST 显式创建首次 index task，并立即展示索引状态。活动任务 SHALL 约每 2 秒从服务端 poll；刷新工作区时 SHALL 通过 owner-scoped background job 列表恢复文档索引任务关联。失败状态 MUST 展示安全 failureReason 并支持 retry；任一文档 MUST 支持手动重建。取消继续由通用 background-job 能力负责，知识页 MUST NOT 创建另一套取消状态机。

#### Scenario: 上传后开始索引
- **WHEN** 文档上传成功
- **THEN** 客户端显式调用文档 index-task 创建 API，保存服务端任务 DTO 并对 pending/running 状态约每 2 秒 poll

#### Scenario: 活动任务完成
- **WHEN** poll 返回 succeeded、failed 或 cancelled
- **THEN** 客户端停止该任务的活动轮询、刷新服务端文档列表并显示最终文字状态

#### Scenario: 失败任务重试
- **WHEN** 用户对 failed 或 cancelled 任务选择重试
- **THEN** 客户端调用 retry API，使用返回的新任务替换当前跟踪任务并恢复轮询

#### Scenario: 手动重建
- **WHEN** 文档当前没有活动任务且用户选择重新索引
- **THEN** 客户端调用 create index-task API，不生成假任务或假向量

### Requirement: 预览、覆盖和删除均显式且可恢复
文档详情 MUST 默认折叠，并在展开后从该文档的 chunk-preview endpoint 读取实际切分结果。hash 冲突 MUST 显示明确覆盖确认，只有用户确认后才能以 `overwrite=true` 重新上传；删除 MUST 二次确认。覆盖或删除成功后 MUST 重新读取服务端文档列表。

#### Scenario: 展开行内详情并查看预览
- **WHEN** 用户展开某文档行
- **THEN** 页面在对应行下显示 metadata，并从服务端读取最多 12 段实际 chunk preview

#### Scenario: hash 冲突要求确认
- **WHEN** `overwrite=false` 上传返回 BUSINESS_CONFLICT
- **THEN** 页面保留待上传文件与策略并显示覆盖确认，不自动再次上传

#### Scenario: 用户确认覆盖
- **WHEN** 用户确认覆盖冲突文档
- **THEN** 客户端以相同文件和策略重新上传且 `overwrite=true`，随后显式创建索引任务并刷新列表

#### Scenario: 用户确认删除
- **WHEN** 用户在删除确认中继续
- **THEN** 客户端调用真实 delete API，成功后关闭对应详情并刷新服务端列表

### Requirement: 桌面工作区保持有界滚动和可访问状态
文档列表 MUST 在桌面业务画布的有界区域内独立垂直滚动。行内详情默认折叠；展开后 metadata 与 chunk preview MUST 各自具有有界滚动，长表格 MUST 能横向滚动且不得撑坏整页。loading、empty、error、index status 和确认操作 MUST 使用可见中文文字与适当 ARIA，不能只依赖颜色；不得新增移动专用导航或替代流程。

#### Scenario: 长内容保持工作区边界
- **WHEN** 文档、metadata、预览段落或表格内容超过可用桌面空间
- **THEN** 对应内部区域滚动且 WorkspaceLayout 与页面宽高保持稳定

#### Scenario: 辅助技术识别状态
- **WHEN** 页面正在加载、为空、失败或显示索引状态
- **THEN** 用户可见中文文字与 role、aria-live 或可访问名称共同表达状态
