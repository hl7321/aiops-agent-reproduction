# Linux 本地安装

1. 用发行版包管理器安装 Git、Docker Engine 与 Docker Compose plugin，并让当前用户有权执行 Docker。
2. 安装 Node.js LTS/npm 和 uv；验证 `git`、`docker compose`、`node`、`npm`、`uv`。
3. 官方 CLS MCP 通过 `npx -y cls-mcp-server@latest` 在主机运行，需要 `TENCENTCLOUD_SECRET_ID` 与 `TENCENTCLOUD_SECRET_KEY`；启动脚本只从 ignored JSON 向该子进程传递它们。
4. 复制配置模板后运行 `./scripts/start-local.sh`。若服务器无桌面浏览器，可从本机访问映射端口或分别启动进程。

普通启动不执行任何 fixture 外部写入。官方 CLS MCP 说明见 <https://github.com/Tencent/cls-mcp-server>。
