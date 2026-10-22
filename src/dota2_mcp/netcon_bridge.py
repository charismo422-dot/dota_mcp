"""Module 5: TCP NetCon bridge to running Dota 2 (-netconport 2121) for commands and live logs."""

from __future__ import annotations

import os
import socket
import time
from typing import Any

from .config import CONFIG


DEFAULT_NETCON_HOST = "127.0.0.1"
DEFAULT_NETCON_PORT = int(os.environ.get("DOTA2_NETCON_PORT", "2121"))


def check_netcon_open(
    host: str = DEFAULT_NETCON_HOST, port: int = DEFAULT_NETCON_PORT
) -> bool:
    """Return True if Dota 2 NetCon TCP port is listening."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _send_netcon_raw(
    command: str,
    wait_response_ms: int = 1200,
    host: str = DEFAULT_NETCON_HOST,
    port: int = DEFAULT_NETCON_PORT,
) -> list[str]:
    """Send command over NetCon TCP socket and return all non-empty output lines."""
    clean_cmd = command.strip()
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
        return [line.rstrip() for line in raw_output.splitlines() if line.strip()]


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
        lines = _send_netcon_raw(
            clean_cmd, wait_response_ms=wait_response_ms, host=host, port=port
        )
        error_lines = [
            l
            for l in lines
            if any(
                tok in l.lower()
                for tok in (
                    "error",
                    "script runtime error",
                    "stack traceback",
                    "failed",
                    "warning",
                )
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
                f"Ensure Dota 2 Workshop Tools is launched with: -tools -netconport {port} -console -condebug"
            ),
            "disk_console_log_fallback": read_latest_console_log(tail_lines=40),
        }


def verify_vscript_api(search_term: str) -> dict[str, Any]:
    """Query the live Dota 2 engine (7.41+) via 'script_help2 <search_term>' and filter full output before truncation."""
    term = search_term.strip()
    if not term:
        return {"ok": False, "error": "Empty search_term."}

    term_lower = term.lower()
    try:
        all_lines = _send_netcon_raw(f"script_help2 {term}", wait_response_ms=2000)
    except OSError as exc:
        return {
            "ok": False,
            "search_term": term,
            "error": (
                f"Dota 2 must be running with -netconport {DEFAULT_NETCON_PORT} (and a map loaded) "
                f"to query live VScript API via script_help2 ({exc})."
            ),
        }

    # Filter the entire raw buffer on Python side before slicing to 50 lines
    matched_lines = [line for line in all_lines if term_lower in line.lower()]

    # Fallback: if NetCon buffer missed lines written to console.log, also scan console.log
    if not matched_lines and CONFIG.game_dir:
        log_path = CONFIG.game_dir / "dota" / "console.log"
        if log_path.exists():
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
                log_lines = [l.rstrip() for l in log_text.splitlines() if l.strip()]
                matched_lines = [l for l in log_lines[-5000:] if term_lower in l.lower()]
            except Exception:
                pass

    return {
        "ok": True,
        "search_term": term,
        "total_lines_scanned": len(all_lines),
        "matches_count": len(matched_lines),
        "live_engine_matches": matched_lines[:50],
    }


def read_latest_console_log(tail_lines: int = 80) -> dict[str, Any]:
    """Read the tail of game/dota/console.log on disk (useful if NetCon is closed or game crashed)."""
    if not CONFIG.game_dir:
        return {"ok": False, "error": "Dota 2 game_dir not found."}

    log_path = CONFIG.game_dir / "dota" / "console.log"
    if not log_path.exists():
        return {
            "ok": False,
            "error": f"No console.log found at {log_path}. Add '-condebug' to Dota 2 launch options to enable disk logging.",
        }

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        n = max(10, min(tail_lines, 300))
        tail = all_lines[-n:]
        errors = [
            l
            for l in tail
            if any(
                w in l.lower()
                for w in ("error", "script runtime error", "stack traceback", "failed")
            )
        ]
        return {
            "ok": True,
            "log_file": str(log_path),
            "errors_and_warnings": errors[-40:],
            "tail": tail,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
