from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_importing_vector_store_does_not_read_config_create_client_or_connect() -> None:
    script = r'''
import socket
from unittest.mock import patch

import pymilvus

def forbidden(*args, **kwargs):
    raise AssertionError("import 期间不得发生外部 I/O")

with (
    patch("super_ai.project_config.load_project_config", side_effect=forbidden),
    patch("pymilvus.MilvusClient", side_effect=forbidden),
    patch.object(socket.socket, "connect", forbidden),
):
    import super_ai.vector_store
    import super_ai.vector_store.adapter
    import super_ai.vector_store.config
    import super_ai.vector_store.errors
    import super_ai.vector_store.records
    import super_ai.vector_store.schema
    import super_ai.vector_store.types
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_adapter_does_not_publish_fictional_close_lifecycle() -> None:
    from super_ai.vector_store.adapter import MilvusVectorStore

    assert "close" not in MilvusVectorStore.__dict__
