import json
import subprocess
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "config/project.template.json",
    ROOT / "config/user.project.template.json",
)
REQUIRED_CONFIG_SECTIONS = {
    "app",
    "backend",
    "frontend",
    "llm",
    "modelCapabilities",
    "vectorStore",
    "mcp",
    "clsMcpServer",
    "prometheusAlerts",
    "clsLogUpload",
    "aiopsDemo",
}
REQUIRED_AIOPS_DEMO_FIELDS = {
    "backendBaseUrl",
    "email",
    "displayName",
    "password",
    "pollIntervalSeconds",
    "indexWaitSeconds",
}


def test_committed_templates_keep_credentials_empty() -> None:
    for path in TEMPLATES:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        _assert_credentials_empty(cast(dict[object, object], raw), path.name)


def test_committed_templates_expose_final_section_skeleton() -> None:
    for path in TEMPLATES:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        config = cast(dict[object, object], raw)

        assert REQUIRED_CONFIG_SECTIONS <= set(config)
        aiops_demo = config["aiopsDemo"]
        assert isinstance(aiops_demo, dict)
        aiops_items = cast(dict[object, object], aiops_demo)
        aiops_fields = {key for key in aiops_items if isinstance(key, str)}
        assert REQUIRED_AIOPS_DEMO_FIELDS <= aiops_fields


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
        credential_suffixes = ("key", "secret", "token", "password", "secretid")
        if key.lower().endswith(credential_suffixes):
            assert item == "", f"凭据模板值必须为空: {current}"
