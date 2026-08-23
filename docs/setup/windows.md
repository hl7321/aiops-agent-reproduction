# Windows 本地安装

1. 安装 Git for Windows、Docker Desktop、Node.js LTS/npm 与 uv，并重开 cmd/PowerShell 使 PATH 生效。
2. 验证 `git --version`、`docker compose version`、`node --version`、`npm --version`、`uv --version`。
3. 从模板复制 `config\project.json` 与 `config\user.project.json`，只在后者填凭据。
4. 在 cmd 或 PowerShell 运行 `scripts\start-local.bat`。批处理使用 Windows 原生命令与 PowerShell JSON 读取，不要求 Bash；Git Bash 只用于 Unix 脚本路径。
5. 官方 CLS MCP 由 `npx -y cls-mcp-server@latest` 在主机运行，官方说明见 <https://github.com/Tencent/cls-mcp-server>。

必须在真实 Windows cmd/PowerShell 验证 bat；在 macOS/Linux 执行 `bash -n` 不能代表 Windows 验收。
