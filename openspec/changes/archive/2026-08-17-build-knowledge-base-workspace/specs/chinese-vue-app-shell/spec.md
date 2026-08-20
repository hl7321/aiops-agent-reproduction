## MODIFIED Requirements

### Requirement: 工作台提供稳定桌面布局边界
受保护页面 MUST 使用 WorkspaceLayout，并提供左侧 rail 导航、账号与登出入口、顶栏页面标题、具有文字的服务状态和 edge-to-edge 路由画布。会话区域 MUST 只在 Chat 路由显示；其他业务路由 MUST 使用完整业务画布。`/knowledge` MUST 渲染连接真实后端 API 的知识库工作区；仍未实现的业务路由 MUST 保持明确占位。当前验收只面向桌面浏览器，不得新增移动专用抽屉、底部导航或替代流程。

#### Scenario: Chat 显示会话区域
- **WHEN** 已认证用户进入 `/chat`
- **THEN** 工作台同时显示 rail、会话区域和 Chat 路由画布

#### Scenario: 非 Chat 页面使用完整画布
- **WHEN** 已认证用户进入知识库、AIOps 或 MCP 路由
- **THEN** 工作台保留 rail 和顶栏但不显示会话区域，路由内容占用完整业务画布

#### Scenario: 知识库路由使用真实工作区
- **WHEN** 已认证用户进入 `/knowledge`
- **THEN** 路由显示真实知识库工作区并通过共享合同访问服务端数据

#### Scenario: 占位页不声称功能完成
- **WHEN** 用户进入仍未实现产品能力的 AIOps 或 MCP 路由
- **THEN** 页面明确说明该能力将在后续提案实现且不提供虚假的业务操作
