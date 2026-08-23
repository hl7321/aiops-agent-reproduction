# Windows 本地安装

1. 安装 Git for Windows、Docker Desktop、Node.js LTS/npm 与 uv，并重开 cmd/PowerShell 使 PATH 生效。
2. 在 Windows 设置中启用 Developer Mode，或使用具备创建符号链接权限的终端；然后在仓库检出前执行 `git config --global core.symlinks true`。
3. 验证 `git --version`、`docker compose version`、`node --version`、`npm --version`、`uv --version`。
4. 检出仓库后在 PowerShell 执行 `(Get-Item docs\openspec).LinkType`，结果必须为 `SymbolicLink`；再执行 `(Get-Item docs\openspec).Target`，目标必须为 `..\openspec`。
5. 如果链接变成普通文件或目录，确认 Developer Mode 和 `git config --get core.symlinks`，移除错误 checkout 后重新 clone。不得复制 `openspec` 到 `docs`，否则会制造第二事实源。
6. 从模板复制 `config\project.json` 与 `config\user.project.json`，只在后者填凭据。
7. 在 cmd 或 PowerShell 运行 `scripts\start-local.bat`。批处理使用 Windows 原生命令与 PowerShell JSON 读取，不要求 Bash；Git Bash 只用于 Unix 脚本路径。
8. 官方 CLS MCP 由 `npx -y cls-mcp-server@latest` 在主机运行，官方说明见 <https://github.com/Tencent/cls-mcp-server>。

必须在真实 Windows cmd/PowerShell 验证 bat；在 macOS/Linux 执行 `bash -n` 不能代表 Windows 验收。
