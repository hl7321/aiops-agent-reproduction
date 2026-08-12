# Tenant Isolation 规格

## Purpose

本能力为所有后续受保护资源建立不可绕过的 tenant/owner 隔离合同，使本地单用户身份能够安全扩展为多用户数据边界，并同时约束关系数据库与向量检索路径。

## Requirements

### Requirement: 当前用户显式产生 tenant 与 owner scope
认证后的 CurrentUser SHALL 显式产生 OwnerScope 与 tenant context。当前本地模型中 `tenant_id` MUST 等于 `user_id`，但 `tenant_id` 与 `owner_user_id` MUST 作为不同语义字段保留；任一字段为空或二者不一致时 MUST 拒绝构造 scope。

#### Scenario: 从当前用户建立 scope
- **WHEN** 已认证用户进入受保护操作
- **THEN** tenant context 同时包含非空且相等的 `tenant_id` 与 `owner_user_id`

#### Scenario: 拒绝空或不一致 scope
- **WHEN** 调用方提供空 tenant、空 owner 或不相等的 tenant/owner
- **THEN** 系统在访问 Repository、Milvus 或删除路径前拒绝该 scope

### Requirement: 受保护 Repository 在查询语句中强制 owner scope
所有受保护 Repository 方法 MUST 显式接收 `owner_user_id`。读取、更新、删除和父子资源操作 MUST 在同一个数据库语句中同时约束 owner 与资源标识，MUST NOT 先按资源 ID 查询再在 service 层补 owner 检查。Repository 的参数级合同 MUST 可由自动化治理测试验证。

#### Scenario: 两个用户读取同一资源标识
- **WHEN** 用户 B 使用用户 A 的资源 ID 执行 scoped read
- **THEN** 数据库查询同时包含 B 的 owner scope，且不会返回 A 的 record

#### Scenario: 两个用户更新或删除资源
- **WHEN** 用户 B 使用用户 A 的资源 ID 执行 scoped update 或 delete
- **THEN** 受影响行数为零且 A 的资源保持不变

#### Scenario: 父子资源保持同一 owner scope
- **WHEN** 用户访问父资源下的子资源
- **THEN** 查询同时约束 `owner_user_id`、父资源 ID 与子资源 ID，不接受仅按子资源 ID 的查询

### Requirement: 越权错误不可枚举其他用户资源
直接受保护资源的不存在与跨用户访问 MUST 返回相同的 `BUSINESS_RESOURCE_NOT_FOUND` 404，不得泄漏资源 owner 或存在性。受保护父资源不存在或不属于当前用户时 MUST 统一返回 `AUTH_FORBIDDEN` 403，且不得为了区分两者执行第二次无 scope 查询。

#### Scenario: 直接资源不存在与跨用户访问
- **WHEN** 当前用户读取不存在的资源 ID 或另一个用户的资源 ID
- **THEN** 两个响应具有相同 code、HTTP status 与安全消息，且不包含其他用户细节

#### Scenario: 受保护父资源不可访问
- **WHEN** 父资源不存在或属于另一个用户
- **THEN** 子资源操作统一返回 `AUTH_FORBIDDEN` 403，不探测父资源真实 owner

### Requirement: 向量 metadata 保留 tenant 与 owner 语义
写入向量标量或 metadata 时 MUST 同时保存 `tenantId` 与 `ownerUserId`，两者在当前模型中均等于当前 user id。调用方提供的额外 metadata MUST NOT 覆盖 `tenantId`、`ownerUserId`、`knowledgeBaseId` 或 `documentId` 等受保护字段。

#### Scenario: 构建向量 metadata
- **WHEN** 当前用户为知识库文档构建向量 metadata
- **THEN** metadata 同时包含相等的 `tenantId` 与 `ownerUserId`，并保留知识库和文档归属

#### Scenario: 额外 metadata 尝试覆盖 scope
- **WHEN** 可选 metadata 包含受保护字段的新值
- **THEN** 构建过程拒绝输入而不是覆盖可信 scope

### Requirement: Milvus 搜索仅使用允许的 tenant 与知识库 scope
Milvus 搜索 filter MUST 只由 `tenantId` 和 `allowedKnowledgeBaseIds` 构成，其中 tenantId 等于当前 user id。allowed KB 列表为空时 MUST 直接返回空结果且不得创建或连接 Milvus client。可选 document 或 metadata 条件 MUST 在 retrieval tool 完成 scoped 召回后执行，不得扩大或替换 Milvus tenant/KB filter。

#### Scenario: 构建受限搜索 filter
- **WHEN** 当前用户允许访问一个或多个知识库
- **THEN** Milvus filter 仅包含该用户 `tenantId` 与明确允许的 knowledgeBaseId 集合

#### Scenario: 空知识库列表短路
- **WHEN** `allowedKnowledgeBaseIds` 为空
- **THEN** 搜索返回空列表且 Milvus 连接/搜索回调未被调用

#### Scenario: 召回后应用可选条件
- **WHEN** 调用方指定 document 或 metadata 条件
- **THEN** 条件只过滤已通过 tenant/KB scope 召回的结果，不出现在 Milvus scope filter 中

### Requirement: 向量删除必须使用完整非空 scope
删除文档向量 MUST 同时约束 `tenantId`、`knowledgeBaseId` 与 `documentId`。tenant、knowledge base 或 document 任一为空时 MUST 禁止删除；删除 filter MUST NOT 退化为仅 document ID 或无 tenant 的宽范围操作。

#### Scenario: 构建文档向量删除 filter
- **WHEN** 当前用户删除已知知识库中的已知文档向量
- **THEN** delete filter 同时包含 tenant、knowledge base 与 document 三个相等匹配条件

#### Scenario: 拒绝不完整删除 scope
- **WHEN** tenant、knowledge base 或 document 任一标识为空
- **THEN** 系统在调用 Milvus delete 前拒绝操作

### Requirement: 所有后续领域继承同一隔离边界
Chat、Knowledge、Index Jobs、Vector、MCP、AIOps、Evidence、Reports、Cases、Feedback、Audit 和 Background Jobs 的受保护数据访问 MUST 使用 CurrentUser/OwnerScope、scoped Repository 与相同的 tenant filter 约定，不得声明隐式全局 tenant 或绕过 scope helper。

#### Scenario: 后续领域新增受保护 Repository
- **WHEN** 后续 change 新增任一列出的领域 Repository 或后台任务
- **THEN** 其合同、实现和测试显式携带 owner/tenant scope，并通过参数级治理检查
