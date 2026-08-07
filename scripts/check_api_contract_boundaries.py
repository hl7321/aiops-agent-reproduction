"""阻止应用代码绕过 packages/api-contracts 自造 HTTP/SSE 结构。"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SSE_EVENT_TYPES = frozenset(
    {
        "content.delta",
        "reasoning.delta",
        "tool.call",
        "reference.source",
        "task.status",
        "report",
        "complete",
        "error",
    }
)
TYPESCRIPT_STRING = re.compile(r"(['\"])(?P<value>[^'\"]+)\1")
TYPESCRIPT_ENVELOPE = re.compile(
    r"\bok\s*:\s*(?:true|false).+\b(?:data|error)\s*:.+\bmeta\s*:",
    re.DOTALL,
)


def find_violations(root: Path) -> list[str]:
    """返回仓库生产源码中的合同边界违规。"""
    violations: list[str] = []
    frontend_root = root / "apps/frontend/src"
    backend_root = root / "apps/backend/src"

    for path in sorted(frontend_root.rglob("*.ts")) if frontend_root.exists() else ():
        if path.name.endswith(".test.ts"):
            continue
        text = path.read_text(encoding="utf-8")
        values = {match.group("value") for match in TYPESCRIPT_STRING.finditer(text)}
        if values & SSE_EVENT_TYPES:
            violations.append(format_violation(root, path, "私有 SSE 事件字面量"))
        if TYPESCRIPT_ENVELOPE.search(text) is not None:
            violations.append(format_violation(root, path, "临时 HTTP envelope"))

    for path in sorted(backend_root.rglob("*.py")) if backend_root.exists() else ():
        if path.name == "api_contracts.py" or path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        if literals & SSE_EVENT_TYPES:
            violations.append(format_violation(root, path, "私有 SSE 事件字面量"))
        if any(is_temporary_envelope(node) for node in ast.walk(tree)):
            violations.append(format_violation(root, path, "临时 HTTP envelope"))

    return violations


def is_temporary_envelope(node: ast.AST) -> bool:
    """识别直接拼装的成功或失败 envelope 字典。"""
    if not isinstance(node, ast.Dict):
        return False
    keys = {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    return {"ok", "meta"} <= keys and ("data" in keys or "error" in keys)


def format_violation(root: Path, path: Path, reason: str) -> str:
    return f"{path.relative_to(root)}: {reason}；请扩展 packages/api-contracts 并使用共享 helper"


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("用法: check_api_contract_boundaries.py <repository-root>")
        return 2
    root = Path(arguments[0]).resolve()
    if not root.is_dir():
        print(f"仓库目录不存在: {root}")
        return 2

    violations = find_violations(root)
    if violations:
        print("\n".join(violations))
        return 1
    print("API/SSE 合同边界检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
