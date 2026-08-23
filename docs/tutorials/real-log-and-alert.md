# 真实日志、告警与 AIOps 演示

本教程包含真实外部副作用。只有在你确认使用自己的 CLS topic、Alertmanager 和测试账号后，才逐条执行；普通启动不会调用这些命令。

1. 在 ignored `config/user.project.json` 填 `clsLogUpload`、`aiopsDemo`、Qwen、Milvus 与 `clsMcpServer`。
2. 启动五服务和主机应用，确认 `/config/check` 为 ready。
3. 显式上传十场景合成日志：

   ```bash
   uv run --locked --script scripts/generate_and_upload_cls_logs.py \
     --profile java-ecommerce --confirm-target
   ```

4. 显式向你选择的 Alertmanager 发布告警：

   ```bash
   python scripts/publish_java_ecommerce_alerts.py \
     --alertmanager-url http://127.0.0.1:9093 --confirm-target
   ```

5. 显式上传并等待十份 SOP 索引：

   ```bash
   python scripts/seed_java_ecommerce_aiops_sops.py --confirm-target
   ```

6. 在桌面完成：注册/登录 → 持久 Chat/SSE → 上传 MD/PDF 并索引 → 自主知识/MCP 工具 → 活跃告警 → CLS 诊断 → 证据/报告 → 案例知识 → 反馈。

任一步失败都应停止并查看脱敏错误，不能把部分成功写成完整验收通过。自动 fake transport 测试不等于 CLS、Qwen、Milvus 或官方 MCP 真实连通；缺失项必须记录“未执行”。
