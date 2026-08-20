# 中文 Vue 应用壳规格

## Purpose

本能力定义面向桌面浏览器的中文 Vue 认证工作台壳，使后续业务页面共享一致的路由保护、布局、状态清理、反馈和可访问交互边界，而不提前宣称业务能力已经完成。

## Requirements

### Requirement: 路由区分公共认证页和受保护工作台
系统 SHALL 将 `/login` 与 `/register` 定义为 publicOnly 路由，将 `/chat`、`/knowledge`、`/aiops` 与 `/mcp` 放入受保护的工作台布局。`/` MUST 重定向到 `/chat`，未知路由 MUST 回到 `/chat`。

#### Scenario: 未登录用户访问受保护路由
- **WHEN** 未认证用户访问任一受保护路由及其 query
- **THEN** 系统导航到 `/login` 并以安全的站内 redirect 参数保留原目标

#### Scenario: 已登录用户访问认证页
- **WHEN** 已认证用户访问 `/login` 或 `/register`
- **THEN** 系统导航到 `/chat`

#### Scenario: 根路径和未知路径归一化
- **WHEN** 用户访问 `/` 或未知路径
- **THEN** 路由最终进入受保护的 `/chat` 流程

### Requirement: 首次导航只恢复认证一次
路由守卫 MUST 在首次导航完成前等待 `auth.initialize()`，并在同一应用实例生命周期中至多启动一次恢复调用。存在 bearer token 时恢复 MUST 使用真实 `/auth/me`；无 token 时 SHALL 直接进入匿名状态。

#### Scenario: 多次导航只初始化一次
- **WHEN** 同一应用实例连续发生首次和后续导航
- **THEN** 守卫只启动一次认证初始化且每次导航均依据初始化后的认证状态决策

#### Scenario: 刷新恢复工作台
- **WHEN** 浏览器已有有效 token 并刷新受保护路由
- **THEN** `/auth/me` 成功后用户停留在目标工作台路由

### Requirement: 认证表单连接真实认证服务
登录和注册页面 MUST 调用共享 Auth DTO 对应的真实 P04 API client。登录成功 SHALL 进入经过校验的站内 redirect 或 `/chat`；注册成功 SHALL 使用同一组凭据登录并进入工作台。认证错误 SHALL 以文字反馈呈现。

#### Scenario: 登录后返回原受保护路由
- **WHEN** 用户从受保护路由被引导至登录页并提交有效凭据
- **THEN** 系统调用 `/auth/login` 并返回原站内路由

#### Scenario: 注册后进入工作台
- **WHEN** 用户提交有效注册资料且注册和随后登录均成功
- **THEN** 系统建立认证状态并导航到 `/chat`

### Requirement: 工作台提供稳定桌面布局边界
受保护页面 MUST 使用 WorkspaceLayout，并提供左侧 rail 导航、账号与登出入口、顶栏页面标题、具有文字的服务状态和 edge-to-edge 路由画布。会话区域 MUST 只在 Chat 路由显示；其他业务路由 MUST 使用完整业务画布。`/knowledge` MUST 渲染连接真实后端 API 的知识库工作区，`/mcp` MUST 渲染以服务器为事实来源的 MCP 连接管理工作区；仍未实现的 AIOps 路由 MUST 保持明确占位。当前验收只面向桌面浏览器，不得新增移动专用抽屉、底部导航或替代流程。

#### Scenario: Chat 显示会话区域
- **WHEN** 已认证用户进入 `/chat`
- **THEN** 工作台同时显示 rail、会话区域和 Chat 路由画布

#### Scenario: 非 Chat 页面使用完整画布
- **WHEN** 已认证用户进入知识库、AIOps 或 MCP 路由
- **THEN** 工作台保留 rail 和顶栏但不显示会话区域，路由内容占用完整业务画布

#### Scenario: 知识库路由使用真实工作区
- **WHEN** 已认证用户进入 `/knowledge`
- **THEN** 路由显示真实知识库工作区并通过共享合同访问服务端数据

#### Scenario: MCP 路由使用真实工作区
- **WHEN** 已认证用户进入 `/mcp`
- **THEN** 路由显示真实 MCP 连接列表、编辑与检查交互，不渲染静态演示数据

#### Scenario: 占位页不声称功能完成
- **WHEN** 用户进入仍未实现产品能力的 AIOps 路由
- **THEN** 页面明确说明该能力将在后续提案实现且不提供虚假的业务操作

### Requirement: 受保护客户端数据具有统一清理边界
系统 SHALL 提供 Pinia store 清理注册机制和内存态 protectedData。401、认证失效和 logout MUST 清理所有已注册受保护 store；Chat、知识库与 AIOps 领域数据 MUST NOT 写入 localStorage。logout SHALL 先尝试撤销服务端 session，并且无论请求结果如何都清理客户端状态。

#### Scenario: 401 清理受保护 store
- **WHEN** typed API transport 收到共享 401 error envelope
- **THEN** auth 与所有已注册受保护 store 被清理且不调用业务删除 API

#### Scenario: 登出请求失败仍清理本地状态
- **WHEN** 服务端 logout 请求因网络故障失败
- **THEN** 客户端仍移除 token、用户和受保护内存数据并向用户呈现错误

#### Scenario: 领域数据不持久化到浏览器
- **WHEN** protectedData 保存 Chat、知识库或 AIOps 的临时数据
- **THEN** 数据只存在于内存且 localStorage 仍只包含允许的认证 token

### Requirement: 共享状态和反馈不只依赖颜色
系统 MUST 提供 loading、empty、error、feedback 与 async status 共享组件。每种状态 MUST 具有可见中文文字和适当的 ARIA 语义，不得只通过颜色表达。全局反馈 MUST 支持 success、info、error、手动关闭和 3 秒自动消失；新消息 MUST 重置 timer，组件卸载 MUST 清理 timer。

#### Scenario: 状态可被辅助技术识别
- **WHEN** 任一共享状态组件显示
- **THEN** 用户可见文字与 role、aria-live 或等效可访问名称共同表达状态

#### Scenario: 新反馈重置自动关闭时间
- **WHEN** 当前反馈尚未消失时显示一条新反馈
- **THEN** 旧 timer 被取消且新反馈从显示时刻重新计时 3 秒

#### Scenario: 卸载反馈组件
- **WHEN** AppFeedback 在 timer 到期前卸载
- **THEN** 待执行 timer 被清理且不再修改已卸载组件状态

### Requirement: 中文设计基线适配键盘和 reduced motion
桌面工作台 SHALL 使用统一、专业克制的中文设计 tokens 和 Lucide 图标。所有可交互控件 MUST 具有清晰的 focus-visible 样式；用户偏好 reduced motion 时 MUST 禁用非必要动画和过渡。

#### Scenario: 键盘定位交互控件
- **WHEN** 用户使用键盘聚焦导航、按钮、链接或表单控件
- **THEN** 当前焦点具有清晰且不被裁切的视觉指示

#### Scenario: 用户要求减少动态效果
- **WHEN** 浏览器报告 `prefers-reduced-motion: reduce`
- **THEN** 工作台取消非必要动画、平滑滚动和过渡
