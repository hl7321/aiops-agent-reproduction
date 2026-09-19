@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "PROJECT_ROOT=%CD%"
set "VAR_DIR=%PROJECT_ROOT%\apps\backend\var"

for %%C in (git docker node npm uv npx powershell) do (
  where %%C >nul 2>nul || (echo 缺少命令 %%C，请先按 docs\setup\windows.md 安装。 & exit /b 1)
)
docker compose version >nul 2>nul || (echo Docker Compose 不可用。 & exit /b 1)

if not exist "config\project.json" copy /Y "config\project.template.json" "config\project.json" >nul
if not exist "config\user.project.json" copy /Y "config\user.project.template.json" "config\user.project.json" >nul
if not exist "%VAR_DIR%" mkdir "%VAR_DIR%"

call npm install || exit /b 1
docker compose -f infra\compose.yaml up -d || exit /b 1
pushd apps\backend
call uv sync || exit /b 1
call uv run alembic upgrade head || exit /b 1
popd

for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$p=Get-Content 'config/project.json' -Raw|ConvertFrom-Json;$u=Get-Content 'config/user.project.json' -Raw|ConvertFrom-Json;if($u.clsMcpServer.secretId){$u.clsMcpServer.secretId}else{$p.clsMcpServer.secretId}"`) do set "CLS_SECRET_ID=%%V"
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$p=Get-Content 'config/project.json' -Raw|ConvertFrom-Json;$u=Get-Content 'config/user.project.json' -Raw|ConvertFrom-Json;if($u.clsMcpServer.secretKey){$u.clsMcpServer.secretKey}else{$p.clsMcpServer.secretKey}"`) do set "CLS_SECRET_KEY=%%V"

if defined CLS_SECRET_ID if defined CLS_SECRET_KEY (
  set "TRANSPORT=http"
  rem 端口必须是 3001：3000 已被 infra 里的 Attu 占用，配置里的 clsMcpServer.baseUrl 也指向 3001。
  set "PORT=3001"
  set "TZ=Asia/Shanghai"
  set "TENCENTCLOUD_SECRET_ID=%CLS_SECRET_ID%"
  set "TENCENTCLOUD_SECRET_KEY=%CLS_SECRET_KEY%"
  start "CLS MCP" /B cmd /C "npx -y cls-mcp-server@latest 1>\"%VAR_DIR%\cls-mcp-server.log\" 2>&1"
) else (
  echo 未配置 CLS MCP 凭据：跳过该进程，/ready 将报告 unavailable。
)

start "Backend" /B cmd /C "uv --directory apps/backend run uvicorn super_ai.app:create_local_app --factory --host 127.0.0.1 --port 8000 1>\"%VAR_DIR%\backend.log\" 2>&1"
start "Frontend" /B cmd /C "npm run frontend:dev -- --host 127.0.0.1 1>\"%VAR_DIR%\frontend.log\" 2>&1"
echo 本地服务已启动：Frontend http://127.0.0.1:5173，Backend http://127.0.0.1:8000
echo 普通启动不会上传 CLS 日志、发布告警或 seed SOP。
endlocal
