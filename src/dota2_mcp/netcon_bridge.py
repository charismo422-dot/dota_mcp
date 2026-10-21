"""Module 5: TCP NetCon bridge to running Dota 2 (-netconport 29000) for commands and live logs."""

from __future__ import annotations

import os
import socket
import time
from typing import Any


DEFAULT_NETCON_HOST = "127.0.0.1"
DEFAULT_NETCON_PORT = int(os.environ.get("DOTA2_NETCON_PORT", "29000"))


def check_netcon_open(
    host: str = DEFAULT_NETCON_HOST, port: int = DEFAULT_NETCON_PORT
) -> bool:
    """Return True if Dota 2 NetCon TCP port is listening."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def run_console_command(
    command: str,
    wait_response_ms: int = 1200,
    host: str = DEFAULT_NETCON_HOST,
    port: int = DEFAULT_NETCON_PORT,
) -> dict[str, Any]:
    """Send a console command to Dota 2 via NetCon TCP socket and collect console output."""
    clean_cmd = command.strip()
    if not clean_cmd:
        return {"ok": False, "error": "Empty console command."}

    try:
        with socket.create_connection((host, port), timeout=3.0) as sock:
            sock.setblocking(False)
            # Drain any stale buffer first
            try:
                while sock.recv(65536):
                    pass
            except BlockingIOError:
                pass

            payload = (clean_cmd + "\n").encode("utf-8")
            sock.sendall(payload)

            deadline = time.monotonic() + max(100, min(wait_response_ms, 15000)) / 1000.0
            chunks: list[bytes] = []
            while time.monotonic() < deadline:
                try:
                    data = sock.recv(16384)
                    if not data:
                        break
                    chunks.append(data)
                except BlockingIOError:
                    time.sleep(0.05)

            raw_output = b"".join(chunks).decode("utf-8", errors="replace")
            lines = [line.rstrip() for line in raw_output.splitlines() if line.strip()]
            error_lines = [
                l
                for l in lines
                if any(
                    tok in l.lower()
                    for tok in ("error", "script runtime error", "stack traceback", "failed", "warning")
                )
            ]

            return {
                "ok": True,
                "command": clean_cmd,
                "lines_received": len(lines),
                "errors_and_warnings": error_lines[-40:],
                "console_tail": lines[-50:],
            }
    except OSError as exc:
        return {
            "ok": False,
            "command": clean_cmd,
            "error": (
                f"Could not connect to Dota 2 NetCon at {host}:{port} ({exc}). "
                "Ensure Dota 2 Workshop Tools is launched with: -tools -netconport 29000 -console"
            ),
        }
