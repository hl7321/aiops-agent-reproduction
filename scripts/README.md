# 脚本目录

本目录用于跨 workspace 的可重复维护脚本。`check_api_contract_boundaries.py` 会检查应用生产源码，阻止在共享合同之外复制 SSE 事件字面量或直接拼装 HTTP envelope；仓库 pytest 门禁会用受控 fixture 和当前仓库执行该脚本。

## 人工生成并上传 CLS 日志

`generate_and_upload_cls_logs.py` 是独立的人工工具，不会被应用启动、模块导入或测试自动执行。它使用脚本自己的 PEP 723 依赖和 lock，避免腾讯 CLS SDK 的旧版 protobuf 约束污染后端依赖图。

凭据和目标只能填写在被 Git 忽略的 `config/user.project.json` 的 `clsLogUpload` 中；脚本先读取 `config/project.json`，再用用户配置递归深合并。禁止用环境变量传入项目配置，也禁止提交 `secretId`、`secretKey`。`region` 会写入每条日志，`logsetId` 只供人工核对，SDK 实际路由由 HTTPS `endpoint` 决定，上传目标为 `topicId`。

真实执行会向外部 CLS 写入数据。必须先人工确认 endpoint、region、logsetId、topicId 属于自己的目标，再显式运行：

```bash
uv run --locked --script scripts/generate_and_upload_cls_logs.py \
  --count 20 \
  --confirm-target
```

`count` 只能为 1 到 100。脚本只生成有界、无密钥的结构化样例日志，控制台只输出数量和 requestId，不打印凭据。macOS 若在首次创建脚本隔离环境时无法构建 `python-snappy`，需要先由使用者自行安装 Snappy 开发库；这不影响后端安装、启动或自动化门禁。
