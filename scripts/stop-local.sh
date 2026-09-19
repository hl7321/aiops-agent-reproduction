#!/usr/bin/env bash
# 停止本地开发服务：先按 PID 文件停，再按端口兜底。
# 端口固定为 后端 8000 / 前端 5173 / 官方 CLS MCP 3001（Attu 的 3000 归容器，不在这里动）。
# 默认不碰容器，加 --infra 才会一起 docker compose down（数据卷保留）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VAR_DIR="${PROJECT_ROOT}/apps/backend/var"
COMPOSE_FILE="${PROJECT_ROOT}/infra/compose.yaml"

usage() {
  cat <<'EOF'
用法：./scripts/stop-local.sh [--infra]

  不带参数   只停后端(8000)、前端(5173)、官方 CLS MCP(3001)
  --infra    额外执行 docker compose down，把五个容器也停掉（数据卷保留）
  -h|--help  显示这段说明
EOF
}

stop_by_pid_file() {
  local name="$1" file="$2" pid
  [[ -f "${file}" ]] || return 0
  pid="$(cat "${file}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    echo "已停止 ${name}（PID ${pid}，来自 ${file}）"
  fi
}

stop_by_port() {
  local name="$1" port="$2" pids
  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)"
  [[ -n "${pids}" ]] || return 0
  # 端口上还活着的进程一并停掉：手工启动的服务不会有 PID 文件。
  # shellcheck disable=SC2086
  kill ${pids} 2>/dev/null || true
  echo "已停止 ${name}（端口 ${port}，PID $(echo ${pids} | tr '\n' ' '))"
}

main() {
  local with_infra="no"
  for argument in "$@"; do
    case "${argument}" in
      --infra) with_infra="yes" ;;
      -h|--help) usage; exit 0 ;;
      *) echo "未知参数：${argument}" >&2; usage >&2; exit 2 ;;
    esac
  done

  stop_by_pid_file "后端" "${VAR_DIR}/backend.pid"
  stop_by_pid_file "前端" "${VAR_DIR}/frontend.pid"
  stop_by_pid_file "官方 CLS MCP" "${VAR_DIR}/cls-mcp-server.pid"

  stop_by_port "后端" 8000
  stop_by_port "前端" 5173
  stop_by_port "官方 CLS MCP" 3001

  if [[ "${with_infra}" == "yes" ]]; then
    docker compose -f "${COMPOSE_FILE}" down
    echo "已停止五个容器（数据卷保留）。"
  else
    echo "容器仍在运行；要一起停用 ./scripts/stop-local.sh --infra。"
  fi
}

main "$@"
