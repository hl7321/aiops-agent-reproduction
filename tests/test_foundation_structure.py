import ast
import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]


def test_final_foundation_directories_exist() -> None:
    directories = (
        "apps/backend",
        "apps/frontend",
        "packages/api-contracts",
        "config",
        "infra",
        "scripts",
        "openspec",
        "docs",
    )

    assert all((ROOT / directory).is_dir() for directory in directories)
    assert (ROOT / "apps/backend/src/super_ai/__init__.py").is_file()


def test_root_scripts_cover_workspace_quality_commands() -> None:
    raw: object = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    package = cast(dict[object, object], raw)
    scripts = package.get("scripts")
    assert isinstance(scripts, dict)
    script_map = cast(dict[object, object], scripts)
    script_names = {key for key in script_map if isinstance(key, str)}

    assert {
        "contracts:typecheck",
        "contracts:test",
        "frontend:dev",
        "frontend:typecheck",
        "frontend:test",
        "frontend:build",
        "frontend:test:secret",
        "docs:dev",
        "docs:build",
    } <= script_names


def test_python_sources_never_import_src_super_ai() -> None:
    for path in (ROOT / "apps/backend/src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("src.super_ai") for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("src.super_ai")


def test_application_container_files_are_absent() -> None:
    forbidden = (
        ROOT / "apps/backend/app.Dockerfile",
        ROOT / "apps/frontend/app.Dockerfile",
        ROOT / "project.compose.json",
    )

    assert all(not path.exists() for path in forbidden)
    assert not list(ROOT.glob("**/docker-compose*.yml"))
    assert not list(ROOT.glob("**/docker-compose*.yaml"))


def test_infrastructure_and_readmes_state_current_boundary() -> None:
    infrastructure = (ROOT / "infra/README.md").read_text(encoding="utf-8")
    for service in ("etcd", "MinIO", "Milvus", "Attu", "Alertmanager"):
        assert service in infrastructure
    assert "主机运行" in infrastructure

    readmes = (
        ROOT / "README.md",
        ROOT / "apps/backend/README.md",
        ROOT / "apps/frontend/README.md",
        ROOT / "packages/api-contracts/README.md",
    )
    contents = [path.read_text(encoding="utf-8") for path in readmes]
    assert all("自动化测试" in content or "测试" in content for content in contents)
    assert "当前已实现" in contents[0]
    assert all("AIOps 产品流程尚未实现" not in content for content in contents)
    assert all("实际流式 endpoint 尚未实现" not in content for content in contents)
