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
import super_ai.project_config
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
