import json
import subprocess
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "config/project.template.json",
    ROOT / "config/user.project.template.json",
)


def test_committed_templates_keep_credentials_empty() -> None:
    for path in TEMPLATES:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        _assert_credentials_empty(cast(dict[object, object], raw), path.name)


def test_sensitive_local_files_are_git_ignored() -> None:
    ignored_paths = (
        "config/project.json",
        "config/user.project.json",
        ".env.local",
        ".idea/workspace.xml",
        ".venv/pyvenv.cfg",
        "node_modules/example/package.json",
        "apps/frontend/dist/index.html",
        "coverage/report.json",
        ".pytest_cache/state",
        "docs/.vitepress/cache/metadata.json",
        "docs/.vitepress/dist/index.html",
        "apps/backend/var/runtime.db",
        "runtime.sqlite3",
        "logs/app.log",
    )

    for relative_path in ignored_paths:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0, f"Git 未忽略 {relative_path}"


def _assert_credentials_empty(value: dict[object, object], location: str) -> None:
    for key, item in value.items():
        assert isinstance(key, str)
        current = f"{location}.{key}"
        if isinstance(item, dict):
            _assert_credentials_empty(cast(dict[object, object], item), current)
            continue
        if any(token in key.lower() for token in ("key", "secret", "password")):
            assert item == "", f"凭据模板值必须为空: {current}"
