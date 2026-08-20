from urllib.parse import urlsplit


def validate_mcp_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("MCP URL 必须是具有 host 的 HTTP/HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("MCP URL 不允许包含 userinfo")
    return normalized


def safe_mcp_error(_error: BaseException) -> str:
    """返回不包含 URL、query、凭据或 provider 原始文本的诊断消息。"""
    return "MCP Server 连接失败，请检查服务状态与连接设置"
