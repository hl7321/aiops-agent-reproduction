import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts/check_tenant_repository_boundaries.py"


def run_scanner(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_scanner_rejects_future_repository_without_owner_parameter(tmp_path: Path) -> None:
    repository = tmp_path / "apps/backend/src/super_ai/knowledge/repositories.py"
    repository.parent.mkdir(parents=True)
    repository.write_text(
        "class KnowledgeRepository:\n"
        "    async def get(self, resource_id: str):\n"
        "        return None\n",
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "KnowledgeRepository.get" in result.stdout
    assert "owner_user_id" in result.stdout


def test_scanner_accepts_owner_scoped_future_repository(tmp_path: Path) -> None:
    repository = tmp_path / "apps/backend/src/super_ai/knowledge/repositories.py"
    repository.parent.mkdir(parents=True)
    repository.write_text(
        "class KnowledgeRepository:\n"
        "    async def get(self, owner_user_id: str, resource_id: str):\n"
        "        return None\n",
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_current_repository_obeys_tenant_repository_boundaries() -> None:
    result = run_scanner(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
