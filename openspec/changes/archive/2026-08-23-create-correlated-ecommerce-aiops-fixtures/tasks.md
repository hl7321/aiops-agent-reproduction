## 1. Fixture 合同与纯生成边界

- [x] 1.1 先新增 fixture 目录测试，覆盖固定数量=10、权威 service/incident、所有关联字段唯一、重复生成稳定和安全内容，并运行定向 pytest 观察预期 RED
- [x] 1.2 实现不可变 Java 电商 fixture catalog，以及 CLS record、Alertmanager payload、Markdown SOP 的纯 builder，使目录与关联测试转绿
- [x] 1.3 增加 SOP 可索引结构、文件名、metadata 与跨三类载荷一致性测试并转绿

## 2. CLS profile 兼容扩展

- [x] 2.1 先为 `quant` 默认/count 兼容、`java-ecommerce` 固定十套、Java+count 冲突和完整关联字段新增失败测试
- [x] 2.2 扩展唯一的 `generate_and_upload_cls_logs.py` profile 选择与上传路径，保持既有底层 API、SDK 路由、目标确认和脱敏测试全绿

## 3. Alertmanager 显式发布

- [x] 3.1 先新增告警目标 URL/timeout 校验、十条 v2 payload、显式确认、非 2xx/transport 失败与 import-safety 测试并观察 RED
- [x] 3.2 实现 `publish_java_ecommerce_alerts.py` 的可注入 HTTP transport、fail-fast 安全错误和显式 CLI，使定向测试转绿

## 4. SOP 真实 API seed 与 durable indexing

- [x] 4.1 先新增本地 JSON 深合并、登录/默认 KB/multipart 上传/index task/轮询顺序、失败/超时/冲突/脱敏与 import-safety 测试并观察 RED
- [x] 4.2 实现 `seed_java_ecommerce_aiops_sops.py` 的可注入 API transport、有界轮询和阶段化错误，使定向测试转绿

## 5. 文档、验证与交付

- [x] 5.1 更新 `scripts/README.md`，记录三个脚本的显式副作用边界、固定 Java profile、兼容量化 profile 和人工真实 smoke 顺序
- [x] 5.2 运行脚本定向 pytest、backend 全量 pytest/Ruff/strict Pyright、三个脚本 `py_compile`、`openspec validate --all` 与 `git diff --check`，修复全部问题
- [x] 5.3 使用 `openspec-verify-change` 核对 completeness/correctness/coherence；真实链路未获逐目标确认时明确标记未执行，不用 fake 测试冒充
