## MODIFIED Requirements

### Requirement: 领域边界不暴露 ORM model
领域服务 SHALL 依赖 Repository Protocol 和不可变 record；Protocol 的输入输出 MUST 为 record 或基础标识，不得要求调用方接收 SQLAlchemy ORM model 或 `AsyncSession`。SQLite 相关实现 MUST 位于 `super_ai.memory.sqlite` 或 `super_ai.memory.extended_sqlite`，以允许未来新增 PostgreSQL adapter 而不改变领域服务合同。所有受保护 Repository 方法 MUST 显式接收 `owner_user_id`，SQLite 读取、更新、删除和父子资源语句 MUST 在数据库层应用 owner scope，不得先按资源 ID 查询再补 service 检查。

#### Scenario: SQLite repository 满足共享合同
- **WHEN** 使用测试 record 和测试 ORM model 实现 SQLite repository adapter
- **THEN** 它通过 Repository contract 测试且调用方只观察到不可变 record

#### Scenario: record 不可变
- **WHEN** 调用方尝试修改已经创建的基础 record 字段
- **THEN** 修改被拒绝且 record 保持原值

#### Scenario: 受保护 Repository 参数缺少 owner
- **WHEN** 未来受保护 Repository 的读取、更新、删除或父子方法未声明 `owner_user_id`
- **THEN** 参数级治理测试失败并指出不安全方法

#### Scenario: SQLite 语句携带 owner scope
- **WHEN** 两个用户使用同一资源 ID 执行读取、更新或删除
- **THEN** 每个语句同时约束当前 `owner_user_id`，另一个用户的数据不会被返回或修改
