# 知识库桌面工作区 smoke

## 2026-08-17 执行记录

执行环境：本机 FastAPI、Vite 桌面 Web、真实 SQLite/Auth/Knowledge/Background Jobs API。使用一次性本地账号，结束时已 logout 撤销 session；上传的 smoke 文档均已通过页面确认删除。

已在桌面浏览器完成：

- 注册并登录本地账号，进入受保护的 `/knowledge`；单知识库只显示“默认知识库”，不显示 selector。
- 上传 Markdown，使用 `fixed-character`（1200/200）；服务端返回 `text/markdown` 文档并显式创建 index task。
- 约 2 秒轮询后 Markdown 任务进入 `succeeded`；展开行内详情后，从真实 chunk-preview endpoint 看到 Markdown 正文与 metadata。
- 手动重建 Markdown 后任务再次进入 `succeeded`；重复 hash 上传先显示覆盖确认，确认后新文档成功索引。
- 上传 PDF，使用 `paragraph`；表单不显示也不发送 fixed-character 参数。服务端通过 pypdf 提取文本，实际 preview 显示两段 smoke 正文。
- 两个文档均通过“删除 → 确认删除”调用真实 DELETE API；成功后服务端列表刷新为“暂无知识文档”。
- Milvus 强一致查询确认 Markdown/PDF 删除后对应 documentId 的向量记录均为 0；smoke 结束时所有 `p13-smoke` 向量为 0。
- smoke 期间发现并修复 configured app 仍使用 `NoIndexedVectorDeleter` 的真实 wiring 缺口；现在真实删除端口在调用前显式 initialize Milvus，并始终携带 tenant + KB + document scope。

## 外部索引状态

本机 ignored JSON 已提供有效 Qwen 与 Milvus 本地凭据，且两份本机 JSON 均保持 Git ignore。后端通过 `create_configured_app` 注册 `document.index` handler；真实任务完成 Qwen `text-embedding-v4`、Milvus v3.0-beta 1024 维写入、重建替换和 scoped 删除。写入后抽查 3 个 chunk，向量维度均为 1024，`tenantId == ownerUserId` 且所有 scope 非空。

因此，本记录证明 P13 的真实浏览器 UI、HTTP envelope、MD/PDF 上传、任务创建/轮询、Qwen embedding、Milvus insert、实际切分预览、覆盖/重建和删除闭环均已成功执行；未记录或输出任何 API key/token。
