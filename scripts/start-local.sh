#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VAR_DIR="${PROJECT_ROOT}/apps/backend/var"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令 $1。请先按 docs/setup 中对应平台文档安装。" >&2
    exit 1
  fi
}

for command_name in git docker node npm uv npx; do
  require_command "${command_name}"
done
docker compose version >/dev/null

if [[ ! -f "${PROJECT_ROOT}/config/project.json" ]]; then
  cp "${PROJECT_ROOT}/config/project.template.json" "${PROJECT_ROOT}/config/project.json"
fi
if [[ ! -f "${PROJECT_ROOT}/config/user.project.json" ]]; then
  cp "${PROJECT_ROOT}/config/user.project.template.json" "${PROJECT_ROOT}/config/user.project.json"
fi
mkdir -p "${VAR_DIR}"

cd "${PROJECT_ROOT}"
npm install
docker compose -f infra/compose.yaml up -d
(
  cd apps/backend
  uv sync
  uv run alembic upgrade head
)

json_value() {
  node -e '
const fs = require("fs");
const merge = (a, b) => Object.fromEntries(Array.from(new Set([...Object.keys(a), ...Object.keys(b)]))
  .map((k) => [k, a[k] && b[k] && typeof a[k] === "object" &&
    typeof b[k] === "object" && !Array.isArray(a[k]) && !Array.isArray(b[k])
      ? merge(a[k], b[k]) : (k in b ? b[k] : a[k])]));
const base = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const user = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const value = process.argv[3].split(".").reduce((v, k) => v && v[k], merge(base, user));
process.stdout.write(typeof value === "string" ? value : "");
' "${PROJECT_ROOT}/config/project.json" "${PROJECT_ROOT}/config/user.project.json" "$1"
}

CLS_SECRET_ID="$(json_value clsMcpServer.secretId)"
CLS_SECRET_KEY="$(json_value clsMcpServer.secretKey)"
if [[ -n "${CLS_SECRET_ID}" && -n "${CLS_SECRET_KEY}" ]]; then
  # 端口必须是 3001：3000 已被 infra 里的 Attu 占用，配置里的 clsMcpServer.baseUrl 也指向 3001。
  TRANSPORT=http PORT=3001 TZ=Asia/Shanghai \
    TENCENTCLOUD_SECRET_ID="${CLS_SECRET_ID}" \
    TENCENTCLOUD_SECRET_KEY="${CLS_SECRET_KEY}" \
    nohup npx -y cls-mcp-server@latest >"${VAR_DIR}/cls-mcp-server.log" 2>&1 &
  echo "$!" >"${VAR_DIR}/cls-mcp-server.pid"
else
  echo "未配置 clsMcpServer SecretId/SecretKey：跳过官方 CLS MCP，/ready 将明确报告 MCP unavailable。"
fi

nohup uv --directory apps/backend run uvicorn super_ai.app:create_local_app --factory \
  --host 127.0.0.1 --port 8000 >"${VAR_DIR}/backend.log" 2>&1 &
echo "$!" >"${VAR_DIR}/backend.pid"
nohup npm run frontend:dev -- --host 127.0.0.1 \
  >"${VAR_DIR}/frontend.log" 2>&1 &
echo "$!" >"${VAR_DIR}/frontend.pid"

echo "本地服务已启动：Frontend http://127.0.0.1:5173，Backend http://127.0.0.1:8000"
echo "日志与 PID 位于 ${VAR_DIR}。脚本不会上传 CLS 日志、发布告警或 seed SOP。"
