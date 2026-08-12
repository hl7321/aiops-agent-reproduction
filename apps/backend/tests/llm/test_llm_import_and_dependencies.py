from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "apps/backend"


def test_importing_all_llm_modules_does_not_read_config_create_clients_or_connect(
    tmp_path: Path,
) -> None:
    script = """
from unittest.mock import patch

with (
    patch("super_ai.project_config.load_project_config", side_effect=AssertionError("read config")),
    patch("httpx.AsyncClient.__init__", side_effect=AssertionError("create http client")),
    patch("langchain_openai.ChatOpenAI.__init__", side_effect=AssertionError("create chat")),
    patch(
        "langchain_openai.OpenAIEmbeddings.__init__",
        side_effect=AssertionError("create embedding"),
    ),
    patch("socket.socket.connect", side_effect=AssertionError("connect network")),
):
    import super_ai.llm
    import super_ai.llm.config
    import super_ai.llm.errors
    import super_ai.llm.provider
    import super_ai.llm.readiness
    import super_ai.llm.rerank
    import super_ai.llm.types
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_frozen_backend_dependency_graph_does_not_include_dashscope_sdk() -> None:
    result = subprocess.run(
        ["uv", "tree", "--frozen"],
        cwd=BACKEND,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "dashscope" not in result.stdout.lower()
