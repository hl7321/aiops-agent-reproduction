# Tenant 隔离架构

## 当前身份模型

当前本地模型中，认证用户的 `user_id` 同时承担 tenant 和数据 owner 身份：

```text
AuthPrincipal.user.id
  -> CurrentUser.user_id
  -> TenantContext.tenant_id
  -> OwnerScope.owner_user_id
```

三个值当前必须非空且相等，但不可合并成一个隐式全局变量。`tenant_id` 表示检索/数据分区，`owner_user_id` 表示资源归属与审计；未来组织 tenant 可以通过新的 OpenSpec change 扩展，而不删除既有语义字段。

## Repository 边界

所有受保护 Repository 的首个业务参数固定为 `owner_user_id`。读取、更新、删除和父子访问在同一个 SQL 语句中组合 owner 与资源标识：

```text
WHERE owner_user_id = :current_user_id
  AND resource_id = :resource_id
  [AND parent_id = :parent_id]
```

禁止先按 `resource_id` 裸查 ORM，再在 service 层比较 owner。认证 bootstrap Repository 是唯一既有例外：登录必须在 CurrentUser 尚不存在时按规范化邮箱或 token hash 恢复身份；认证成功后的 session mutation 仍绑定 user/session。

直接资源不可见时统一返回 `BUSINESS_RESOURCE_NOT_FOUND` 404，不区分不存在与跨 owner。父资源不可见时统一返回 `AUTH_FORBIDDEN` 403，不执行第二次无 scope 查询探测真实存在性。

## 向量边界

向量标量或 metadata 必须包含：

- `tenantId`：当前 user id，用于 Milvus 强制分区 filter。
- `ownerUserId`：当前 user id，用于归属追溯。
- `knowledgeBaseId` 与 `documentId`：知识库和文档归属。

搜索 filter 只能由 `tenantId + allowedKnowledgeBaseIds` 构成。允许 KB 列表为空时，在创建或连接 Milvus client 前直接返回空结果。可选 document/metadata 条件只能缩小已完成 tenant/KB scoped 召回的结果。

文档向量删除必须使用非空 `tenantId + knowledgeBaseId + documentId` 三条件，禁止只按 document ID 删除或在 tenant 为空时继续操作。

## 适用领域

Chat、Knowledge、Index Jobs、Vector、MCP、AIOps、Evidence、Reports、Cases、Feedback、Audit 和 Background Jobs 的接口、Repository、工具与后台任务都必须显式携带 CurrentUser/OwnerScope。任何新受保护 path 必须在共享 contracts 中先声明 BearerAuth、401 和 403。

logout 只撤销认证 session 并清除客户端可见认证状态，与用户持久数据生命周期正交。
