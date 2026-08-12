## Purpose

本能力为后续领域提供可替换、可测试且导入安全的异步持久化边界，并以可重复迁移、明确事务和规范化数据约定约束 SQLite 的使用方式。

## ADDED Requirements

### Requirement: 数据库配置来自本地 JSON 合并结果
后端 SHALL 从显式传入的 `project.json` 与 `user.project.json` 递归深合并结果中读取数据库 URL，并 MUST NOT 使用 OS 环境变量作为项目数据库配置来源。缺失或无效的数据库配置 MUST 在显式加载时产生可定位的验证错误，而不是在模块导入时失败。

#### Scenario: 用户配置覆盖数据库 URL
- **WHEN** 项目配置与用户配置包含不同的数据库 URL
- **THEN** 数据库 settings 使用用户配置覆盖后的 URL

#### Scenario: 临时配置注入
- **WHEN** 测试传入临时项目配置与用户配置路径
- **THEN** 数据库初始化只使用这些路径的深合并结果且不依赖开发者本机配置

### Requirement: 持久化模块导入无外部副作用
`super_ai.memory` 及其 SQLite adapter SHALL 在导入期间只声明类型、工厂和元数据，MUST NOT 创建 engine、打开数据库文件、建立连接或执行 Alembic 迁移。engine 与 session factory 只能在 FastAPI lifespan、依赖 provider 或调用方显式初始化时创建，并由创建方负责释放。

#### Scenario: 仅导入 memory 包
- **WHEN** 独立 Python 进程导入 `super_ai.memory`、`super_ai.memory.sqlite` 与 `super_ai.memory.extended_sqlite`
- **THEN** 进程成功退出且没有创建 SQLite 文件或运行迁移

#### Scenario: 显式关闭持久化运行时
- **WHEN** 调用方在 lifespan 或显式初始化路径创建并关闭持久化运行时
- **THEN** engine 被释放且后续请求不能继续从已关闭运行时取得 session

### Requirement: Alembic 是 schema 迁移唯一权威
仓库 SHALL 提供异步 Alembic 环境和首个基础 revision。fresh SQLite 数据库执行 `upgrade head` 后 MUST 到达 head，且应用 SQLAlchemy metadata 与迁移产生的业务 schema MUST 一致；运行时代码和应用启动 MUST NOT 使用 `metadata.create_all` 代替迁移。

#### Scenario: fresh database 升级到 head
- **WHEN** migration helper 对一个不存在的临时 SQLite 文件执行 `upgrade head`
- **THEN** 数据库被创建且 Alembic revision 等于当前 head

#### Scenario: metadata 与迁移一致
- **WHEN** fresh 数据库升级到 head 后比较迁移 schema 与应用 metadata
- **THEN** 除 Alembic 自身版本表外不存在缺失表或额外业务表

### Requirement: async session 遵守统一事务约定
后端 SHALL 提供 async engine/session factory 与事务 scope。每个事务 scope MUST 使用独立 session，正常结束时提交，异常时回滚，并在退出时关闭 session；并发协程 MUST 能使用各自 session 操作同一临时 SQLite 数据库。

#### Scenario: 并发 session 相互独立
- **WHEN** 两个异步协程通过同一 session factory 并发执行事务
- **THEN** 两个协程获得不同 session 且各自提交的数据均可在新 session 中读取

#### Scenario: 异常触发回滚
- **WHEN** 事务写入后在 scope 内抛出异常
- **THEN** 该事务的写入不会出现在后续 session 中

### Requirement: 领域边界不暴露 ORM model
领域服务 SHALL 依赖 Repository Protocol 和不可变 record；Protocol 的输入输出 MUST 为 record 或基础标识，不得要求调用方接收 SQLAlchemy ORM model 或 `AsyncSession`。SQLite 相关实现 MUST 位于 `super_ai.memory.sqlite` 或 `super_ai.memory.extended_sqlite`，以允许未来新增 PostgreSQL adapter 而不改变领域服务合同。

#### Scenario: SQLite repository 满足共享合同
- **WHEN** 使用测试 record 和测试 ORM model 实现 SQLite repository adapter
- **THEN** 它通过 Repository contract 测试且调用方只观察到不可变 record

#### Scenario: record 不可变
- **WHEN** 调用方尝试修改已经创建的基础 record 字段
- **THEN** 修改被拒绝且 record 保持原值

### Requirement: 持久化原语具有一致表示
持久化基础 SHALL 统一生成无共享状态的字符串 ID、使用带 UTC 时区的时间，并提供确定性的 JSON 序列化与反序列化。JSON 编码 MUST 拒绝非有限浮点值；未来需要查询、唯一性、外键或关联的数据 MUST 建立规范化列和表，不得塞入无结构的大 JSON 字段。

#### Scenario: JSON 稳定往返
- **WHEN** 同一 JSON object 以不同 key 顺序输入序列化器
- **THEN** 得到相同的规范字符串并可反序列化为等价 JSON 值

#### Scenario: 生成 UTC record
- **WHEN** 创建新的基础 record
- **THEN** ID 非空且时间包含 UTC 时区信息

### Requirement: 测试数据库与开发者数据隔离
仓库 SHALL 提供基于 pytest 临时目录的 SQLite URL 与 migration helper。持久化测试 MUST 使用测试注入的临时数据库，MUST NOT 读取或修改开发者的 `apps/backend/var/memory.sqlite3`。

#### Scenario: 测试运行使用临时数据库
- **WHEN** 执行后端持久化测试
- **THEN** 数据库文件位于该测试的临时目录且开发者默认数据库路径不被创建或修改
