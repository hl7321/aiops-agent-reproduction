import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts/check_api_contract_boundaries.py"


def run_scanner(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_scanner_allows_shared_contract_imports(tmp_path: Path) -> None:
    frontend = tmp_path / "apps/frontend/src/transport.ts"
    backend_contract = tmp_path / "apps/backend/src/super_ai/api_contracts.py"
    frontend.parent.mkdir(parents=True)
    backend_contract.parent.mkdir(parents=True)
    frontend.write_text(
        'import type { SseEvent } from "@super-ai/api-contracts";\n'
        "export function acceptEvent(event: SseEvent): SseEvent { return event; }\n",
        encoding="utf-8",
    )
    backend_contract.write_text(
        'SSE_EVENT_TYPES = ("content.delta", "complete", "error")\n',
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_scanner_rejects_private_frontend_event_union(tmp_path: Path) -> None:
    private_event = tmp_path / "apps/frontend/src/private-events.ts"
    private_event.parent.mkdir(parents=True)
    private_event.write_text(
        'export type PrivateEvent = { type: "content.delta" } | { type: "complete" };\n',
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "private-events.ts" in result.stdout
    assert "私有 SSE 事件字面量" in result.stdout


def test_scanner_rejects_temporary_backend_envelope(tmp_path: Path) -> None:
    route = tmp_path / "apps/backend/src/super_ai/route.py"
    route.parent.mkdir(parents=True)
    route.write_text(
        'def route():\n    return {"ok": True, "data": {}, "meta": {"requestId": "x"}}\n',
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "route.py" in result.stdout
    assert "临时 HTTP envelope" in result.stdout


def test_scanner_rejects_private_frontend_auth_payload(tmp_path: Path) -> None:
    private_auth = tmp_path / "apps/frontend/src/private-auth.ts"
    private_auth.parent.mkdir(parents=True)
    private_auth.write_text(
        "export interface AuthUser { id: string; email: string; createdAt: string; }\n",
        encoding="utf-8",
    )

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "private-auth.ts" in result.stdout
    assert "私有 Auth payload" in result.stdout


def test_auth_store_persists_only_shared_token_key() -> None:
    source = (ROOT / "apps/frontend/src/stores/auth.ts").read_text(encoding="utf-8")

    assert source.count("storage.setItem(") == 1
    assert "storage.setItem(AUTH_TOKEN_STORAGE_KEY, result.data.token)" in source
    assert "storage.setItem(\"password\"" not in source
    assert "storage.setItem(\"user\"" not in source


def test_current_repository_obeys_contract_boundaries() -> None:
    result = run_scanner(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
