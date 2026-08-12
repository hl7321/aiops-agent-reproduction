## 1. 测试基础与路由认证边界

- [x] 1.1 增加 Vue Test Utils 与 happy-dom 测试依赖并配置组件测试环境
- [x] 1.2 先编写 publicOnly、protected、redirect、未知路由和一次性认证恢复测试，确认 RED
- [x] 1.3 实现 typed route meta、router factory 与等待认证恢复的全局守卫
- [x] 1.4 扩展 auth store 的幂等 initialize、注册后登录和安全本地清理行为
- [x] 1.5 为 typed apiClient 增加共享 401 清理扩展点并回归 SSE typed transport

## 2. 受保护 store 与共享交互状态

- [x] 2.1 先编写 cleanup registry、protectedData 内存态和禁止领域 localStorage 的测试，确认 RED
- [x] 2.2 实现可注册/注销/批量执行的受保护 store cleanup registry 与 protectedData store
- [x] 2.3 先编写 loading、empty、error、async status 的文字和 ARIA 测试，确认 RED
- [x] 2.4 实现共享 AppLoadingState、AppEmptyState、AppErrorState 与 AsyncStatusBadge
- [x] 2.5 先编写 feedback 手动关闭、3 秒自动消失、新消息重置和 unmount 清理测试，确认 RED
- [x] 2.6 实现 feedback store 与全局 AppFeedback

## 3. 真实认证页面与桌面工作台

- [x] 3.1 先编写登录/注册真实 store 调用、认证恢复和 logout 清理的交互测试，确认 RED
- [x] 3.2 实现中文登录/注册表单、错误反馈和安全 redirect
- [x] 3.3 先编写 rail、Chat 专属会话区域、顶栏、账号、服务状态和 edge-to-edge 画布测试，确认 RED
- [x] 3.4 实现 WorkspaceLayout、Chat 画布和 knowledge/AIOps/MCP 明确占位页面
- [x] 3.5 使用 Lucide 图标、设计 tokens、focus-visible 与 prefers-reduced-motion 完成桌面视觉基线
- [x] 3.6 更新前端入口与 README，只说明已经实现的应用壳和验证方式

## 4. 工程门禁与浏览器验收

- [x] 4.1 运行 frontend typecheck/test/build 并修复全部问题
- [x] 4.2 运行 contracts typecheck/test 与相关 backend auth tests
- [x] 4.3 在桌面浏览器检查登录/注册和工作台布局、可见反馈及键盘焦点
- [x] 4.4 运行 openspec validate --all 与 git diff --check

## 5. OpenSpec 验证与归档

- [x] 5.1 使用 openspec-verify-change 核对完整性、正确性和设计一致性，修复所有 CRITICAL 并处理 WARNING
- [x] 5.2 修复后重新运行所有受影响门禁并记录真实结果
- [x] 5.3 同步 chinese-vue-app-shell 与 user-authentication delta specs 到主规格
- [x] 5.4 归档 build-chinese-vue-app-shell 并再次运行 openspec validate --all 和 git diff --check
