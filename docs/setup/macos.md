# macOS 本地安装

1. 安装 Git、Docker Desktop（含 Compose）、Node.js LTS/npm 与 uv。
2. 验证：`git --version`、`docker compose version`、`node --version`、`npm --version`、`uv --version`。
3. 官方腾讯云 CLS MCP 使用 Node.js，通过 `npx -y cls-mcp-server@latest` 在主机运行；不要加入 Compose。
4. 从两份模板复制 ignored JSON，在 `user.project.json` 填个人凭据，然后运行 `./scripts/start-local.sh`。

Apple Silicon 与 Intel 均使用 Compose 中固定镜像。Docker Desktop 必须先启动。官方 CLS MCP 参数以 <https://github.com/Tencent/cls-mcp-server> 为准。
