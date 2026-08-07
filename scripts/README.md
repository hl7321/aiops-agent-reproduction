# 脚本目录

本目录用于跨 workspace 的可重复维护脚本。`check_api_contract_boundaries.py` 会检查应用生产源码，阻止在共享合同之外复制 SSE 事件字面量或直接拼装 HTTP envelope；仓库 pytest 门禁会用受控 fixture 和当前仓库执行该脚本。
