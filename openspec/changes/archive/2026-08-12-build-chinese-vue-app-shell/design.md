## Context

当前前端已经有共享 contracts 驱动的 `apiClient`、`sseClient`、`authClient` 和基础 Pinia auth state，但入口在路由之外主动初始化认证，页面仅有 foundation 卡片。P08 需要把这些基础连接成真实可导航、可恢复、可清理的桌面工作台，同时维持 P01 的 public-config allowlist、P02 的 typed transport 和 P04/P05 的认证与 tenant 安全语义。

## Goals / Non-Goals

**Goals:**

- 以 Vue Router 4 的 route meta 建立 publicOnly/protected 边界和一次性认证恢复。
- 以 Pinia 3 建立 auth、feedback、protectedData 与可扩展 store cleanup registry。
- 以 Vue 3.5 组件组合实现桌面 WorkspaceLayout、真实认证表单和可访问共享状态。
- 保持 TypeScript 5.6 strict，包括 `exactOptionalPropertyTypes`、`noUncheckedIndexedAccess`、`isolatedModules`、ES2022/Bundler resolution。
- 继续复用共享 Auth DTO、HTTP envelope 和 SSE union；前端只读取 Vite 注入的公开配置。

**Non-Goals:**

- 不实现 Chat 会话、知识管理、AIOps、MCP 或服务健康探测等产品能力。
- 不新增后端 endpoint、认证过期策略、refresh token 或移动端专用导航。
- 不把任何领域数据或完整配置写入 localStorage，不引入 UI 框架。

## Decisions

### 1. Router factory 与 route meta 共同表达访问策略

生产导出 `createAppRouter()`，测试注入 memory history 和 auth store。受保护路由作为 WorkspaceLayout children；`requiresAuth`、`publicOnly`、页面标题和 Chat 会话区域由 typed route meta 表达。守卫持有单个 initialization promise，避免并发首航重复恢复。

选择原因：路由行为可独立测试，布局边界与访问边界保持一致。备选是在每个页面内执行 redirect，但会产生闪烁、重复请求和遗漏保护。

### 2. 认证 store 保证 initialize 幂等，transport 提供 401 回调

auth store 缓存初始化 promise；路由守卫只调用公开 `initialize()`。`apiClient` 在解析共享失败 envelope 后，对 401 调用可注入 `onUnauthorized`，生产 client 将其连接到统一的本地清理入口。认证恢复自身的 401 仍由 auth store 收敛为 anonymous。

选择原因：401 可能来自后续任意受保护 endpoint，不能只在页面捕获。备选是全局事件总线，但类型与生命周期更隐晦。

### 3. cleanup registry 清理内存 store，auth token 保持唯一持久凭据

cleanup registry 保存幂等回调并返回注销函数。protectedData 作为后续 store 的示例和统一 transient state，只使用 Pinia 内存；auth 在失效和 logout 的 finally 路径调用 registry。不得读取或写入 Chat、知识库、AIOps 的 localStorage key。

选择原因：后续领域 store 可注册自身 `$reset`，无需让 auth 依赖具体业务 store。备选是 auth 直接 import 每个 store，会形成循环依赖并随功能增长膨胀。

### 4. WorkspaceLayout 以 CSS grid 提供三种稳定区域

左侧 rail 固定承载主导航和账号动作；Chat route 在 rail 与主画布之间打开会话区域；顶栏和 RouterView 主画布始终属于内容区。非 Chat route 自动折叠为 rail + 完整画布。桌面最小宽度作为本提案验收基线，不提供移动替代 DOM。

选择原因：后续业务页可以 edge-to-edge 管理自己的密度和滚动，不被通用 card 容器限制。备选是所有页面套统一居中容器，不适合 Chat 和运维工作台。

### 5. 共享状态组件通过明确文字、语义和图标表达状态

组件使用 Lucide 图标作为辅助，状态必须同时包含中文文字。feedback store 只保存当前消息；AppFeedback 管理 3 秒 timer、watch 重置和 unmount 清理。全局 CSS tokens 管理颜色、间距、层级、focus ring 和 reduced-motion。

选择原因：timer 与组件生命周期一致，易用 fake timers 验证。备选是在 store 内创建全局 timer，会增加 SSR/测试清理和多 app 实例问题。

### 6. 配置和安全边界保持不变

运行时代码仅通过 `config.ts` 获得 `frontend.title` 与 `frontend.apiBaseUrl`；认证 token 通过 transport 扩展点读取。任何 LLM、CLS、MCP、MinIO 或 vectorStore 配置均不进入组件或 bundle。

选择原因：延续 P01 sentinel secret 扫描证明，P08 不增加新的公开字段或环境变量配置路径。

## Risks / Trade-offs

- [首次 `/auth/me` 网络错误无法判断是否登录] → 保留 token 和 error 状态，路由按未认证处理并在登录页展示可重试错误；不把网络错误误判为凭据失效。
- [logout 网络失败但服务端 session 仍有效] → 客户端必须清理并反馈失败；不虚构撤销成功，用户可重新登录后再次撤销。
- [registry 回调抛错中断其他 store 清理] → registry 对每个回调独立执行并在完成后聚合/报告，确保其余 store 仍被清理。
- [桌面最小宽度在窄屏产生横向滚动] → 这是明确的 P08 验收边界，后续移动体验需要独立提案。
- [占位路由被误认为业务已完成] → 文案明确“将在后续提案实现”，不提供虚假按钮、数据或服务在线结论。

## Migration Plan

1. 增加组件测试运行依赖，不改变生产运行依赖与公开配置。
2. 以新 router、layouts、views 和 stores 替换 foundation 单页入口；保留现有 typed clients 并扩展回调。
3. 运行前端全门禁、contracts 和 P04 后端认证回归；浏览器以桌面视口检查视觉与键盘焦点。
4. 若需回滚，可恢复旧 `main.ts`、`router.ts` 与 `App.vue`，新增模块没有服务端数据迁移或不可逆操作。
