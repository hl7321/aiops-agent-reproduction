import subprocess
import sys


def test_import_does_not_open_database_or_network_connections() -> None:
    script = """
import socket
import sqlite3

def blocked(*args, **kwargs):
    raise AssertionError("import attempted external connection")

sqlite3.connect = blocked
socket.socket.connect = blocked

import super_ai
import super_ai.app
import super_ai.background_jobs
import super_ai.background_jobs.handlers
import super_ai.background_jobs.runtime
import super_ai.chat
import super_ai.chat.router
import super_ai.knowledge
import super_ai.knowledge.chunking
import super_ai.knowledge.files
import super_ai.document_indexing.dependencies
import super_ai.document_indexing.factory
import super_ai.document_indexing.handler
import super_ai.document_indexing.models
import super_ai.document_indexing.router
import super_ai.document_indexing.service
import super_ai.retrieval
import super_ai.retrieval.bm25
import super_ai.retrieval.corpus
import super_ai.retrieval.factory
import super_ai.retrieval.fusion
import super_ai.retrieval.service
import super_ai.retrieval.tokenizer
import super_ai.retrieval.tool
import super_ai.project_config
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
