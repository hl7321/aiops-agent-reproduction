"""阻止未来受保护 Repository 缺少显式 owner scope 参数。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

AUTH_BOOTSTRAP_EXEMPTIONS = frozenset(
    {
        "super_ai/auth/repositories.py",
        "super_ai/memory/repository.py",
        "super_ai/memory/extended_sqlite/repository.py",
        "super_ai/memory/extended_sqlite/auth_repositories.py",
    }
)


def find_violations(root: Path) -> list[str]:
    source_root = root / "apps/backend/src"
    violations: list[str] = []
    if not source_root.exists():
        return violations

    for path in sorted(source_root.rglob("*.py")):
        relative_source = path.relative_to(source_root).as_posix()
        if relative_source in AUTH_BOOTSTRAP_EXEMPTIONS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Repository"):
                continue
            for method in node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name.startswith(
                    "_"
                ):
                    continue
                parameters = [*method.args.posonlyargs, *method.args.args]
                if len(parameters) < 2 or parameters[1].arg != "owner_user_id":
                    location = path.relative_to(root)
                    violations.append(
                        f"{location}:{method.lineno}: {node.name}.{method.name} "
                        "的首个业务参数必须是 owner_user_id"
                    )
    return violations


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("用法: check_tenant_repository_boundaries.py <repository-root>")
        return 2
    root = Path(arguments[0]).resolve()
    if not root.is_dir():
        print(f"仓库目录不存在: {root}")
        return 2
    violations = find_violations(root)
    if violations:
        print("\n".join(violations))
        return 1
    print("Tenant Repository owner scope 检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
