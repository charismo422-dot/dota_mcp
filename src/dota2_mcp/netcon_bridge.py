"""Module 5: TCP NetCon bridge to running Dota 2 (-netconport 2121) for commands and live logs."""

from __future__ import annotations

import os
import re
import socket
import time
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG


DEFAULT_NETCON_HOST = "127.0.0.1"
DEFAULT_NETCON_PORT = int(os.environ.get("DOTA2_NETCON_PORT", "2121"))

REPO_ROOT = Path(__file__).resolve().parents[2]
VSCRIPT_CACHE_DIR = REPO_ROOT / ".cache" / "vscript_api"

# "10/22 19:21:30 " prefix of console.log lines
TIMESTAMP_RE = re.compile(r"^\d\d/\d\d \d\d:\d\d:\d\d ")

ERROR_TOKENS = ("error", "script runtime error", "stack traceback", "failed", "warning", "attempt to")

# Engine chatter that never concerns the addon (verified on 7.41 build 6965 with mcp_lab).
NOISE_PATTERNS = re.compile(
    "|".join(
        [
            r"^server_\w+:", r"^relays?_", r"^tv_secret_code:", r"^build_version:", r"^allow_custom_games:",
            r"^assigned_server_tv_port:", r"^---$", r"Sent CMsgGameServerInfo", r"\b(Send|Recv) msg \d+",
            r"PR:\w+", r"Gamerules: entering state", r"EventGameRulesStateChanged", r"LoadingDisplay changed",
            r"STEAM USERID validated", r"m_fl\w+Time set to", r"GC connection established\.\s+This is guaranteed", r"Tick packet desired", r"\[(NetSteamConn|Networking|SteamNetSockets|SplitScreen|stringtables|AnimResource|SOCache|GCClient|Prediction|SignonState|EngineServiceManager)\]",
            r"Bot ward spot", r"^\*\*\*\* Panel", r"CL:\s+(pending|prerequisite|waiting|sequential|firstspawngroup|\s*:)",
            r"SteamRemoteStorage", r"CAsyncWriteInProgress", r"IGameSystem::Loop", r"CRecipientFilter",
            r"PERF WARNING", r"broadcastfacts_", r"DOTANeutralItems", r"npc_neutral_items_custom\.txt",
            r"response_rules_custom\.txt", r"FindSafe failed to localize: 'invalid index'", r"m_hSteamPipe == 0",
            r"Unable to lookup attachment \"attach_hitloc\" on model \"\"", r"Error creating shader generic\.vfx",
            r"Failed loading resource \"(materials/particle/particle_ring_blurry|materials/sprites/blueglow1|particles/neutral_fx/miniboss|panorama/images/players/|panorama/images/heroes/icons/npc_dota_hero_announcer|maps/[^/]+/world_visibility\.vvis_c)",
            r"AuthStatus", r"Certificate expires", r"OnSteamServersConnected", r"GC Connection established",
            r"Received server welcome", r"ResetBreakpadAppId", r"SteamGameServer_Init", r"Client missing networkable entity class",
            r"msec change '", r"LoopActivateAllSystems",
            r"DepthPassBatchID", r"can't solve quadratic for light", r"OnHltvReplay", r"Signon traffic",
            r"NetChan Setting Timeout", r"received full update", r"Resetting prediction state", r"non-incremental update",
            # script_help2 API dump lines (served from the verify_vscript_api cache instead)
            r"^(\[VScript\] ?)?(---\[\[|-- @|--- Enum|function .*\) end$|[A-Za-z_][A-Za-z0-9_]* = -?\d+( --.*)?$|$)", r"^(Server|Client):\s+(Inactive|Disconnected)", r"@ Current\s+:", r"Queued\s+:",
        ]
    )
)


def _strip_timestamp(line: str) -> str:
    return TIMESTAMP_RE.sub("", line, count=1)


def _filter_console_lines(lines: list[str], verbose: bool = False) -> tuple[list[str], list[str], int]:
    """Return (meaningful_lines, error_lines, hidden_noise_count) with timestamps stripped."""
    cleaned = [_strip_timestamp(l) for l in lines]
    if verbose:
        kept = cleaned
    else:
        kept = [l for l in cleaned if not NOISE_PATTERNS.search(l)]
    errors = [l for l in kept if any(tok in l.lower() for tok in ERROR_TOKENS)]
    return kept, errors, len(cleaned) - len(kept)


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
    verbose: bool = False,
) -> dict[str, Any]:
    """Send a console command to Dota 2 via NetCon TCP socket and collect console output.

    Known engine noise is hidden unless verbose=True.
    """
    clean_cmd = command.strip()
    if not clean_cmd:
        return {"ok": False, "error": "Empty console command."}

    try:
        lines = _send_netcon_raw(
            clean_cmd, wait_response_ms=wait_response_ms, host=host, port=port
        )
        kept, errors, hidden = _filter_console_lines(lines, verbose=verbose)

        return {
            "ok": True,
            "command": clean_cmd,
            "lines_received": len(lines),
            "noise_lines_hidden": hidden,
            "errors_and_warnings": errors[-20:],
            "console_tail": kept[-25:],
        }
    except OSError as exc:
        return {
            "ok": False,
            "command": clean_cmd,
            "error": (
                f"Could not connect to Dota 2 NetCon at {host}:{port} ({exc}). "
                f"Ensure Dota 2 Workshop Tools is launched with: -tools -netconport {port} -console -condebug"
            ),
            "disk_console_log_fallback": read_latest_console_log(tail_lines=20),
        }


def _console_log_path() -> Optional[Path]:
    if not CONFIG.game_dir:
        return None
    return CONFIG.game_dir / "dota" / "console.log"


def _game_build() -> str:
    """ClientVersion from game/dota/steam.inf (changes with every Dota 2 patch)."""
    if CONFIG.game_dir:
        steam_inf = CONFIG.game_dir / "dota" / "steam.inf"
        if steam_inf.exists():
            m = re.search(r"^ClientVersion=(\S+)", steam_inf.read_text(errors="replace"), re.MULTILINE)
            if m:
                return m.group(1)
    return "unknown"


def _dump_vscript_api_to_cache(build: str) -> tuple[Optional[Path], str]:
    """Run 'script_help2' once and save its full output (read from console.log) as the API cache."""
    log_path = _console_log_path()
    if not log_path or not log_path.exists():
        return None, "console.log not found; launch Dota 2 with -condebug."

    start = log_path.stat().st_size
    try:
        # NetCon truncates the ~12k-line dump; the complete text is read from console.log instead.
        _send_netcon_raw("script_help2", wait_response_ms=1500)
    except OSError as exc:
        return None, f"Dota 2 NetCon is not reachable on port {DEFAULT_NETCON_PORT} ({exc})."

    # Wait until console.log stops growing
    last, stable_since, deadline = start, time.monotonic(), time.monotonic() + 15
    while time.monotonic() < deadline:
        size = log_path.stat().st_size
        if size != last:
            last, stable_since = size, time.monotonic()
        elif size > start and time.monotonic() - stable_since > 1.0:
            break
        time.sleep(0.2)

    with log_path.open("rb") as f:
        f.seek(start)
        appended = f.read().decode("utf-8", errors="replace")

    api_lines: list[str] = []
    for raw in appended.splitlines():
        if TIMESTAMP_RE.match(raw):
            line = _strip_timestamp(raw)
            if not line.startswith("[VScript] "):
                continue  # unrelated engine output interleaved with the dump
            line = line[len("[VScript] "):]
        else:
            line = raw  # continuation lines of a multi-line VScript message
        api_lines.append(line.rstrip())

    if sum(1 for l in api_lines if l.startswith("function ")) < 500:
        return None, "script_help2 output looks incomplete (load a map first, then retry with refresh=True)."

    VSCRIPT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = VSCRIPT_CACHE_DIR / f"build_{build}.txt"
    cache_file.write_text("\n".join(api_lines) + "\n", encoding="utf-8")
    return cache_file, ""


def _search_vscript_cache(cache_file: Path, term_lower: str, limit: int) -> list[str]:
    """Return compact matches: 'signature  -- description' for functions, the raw line for enums/constants."""
    lines = cache_file.read_text(encoding="utf-8", errors="replace").splitlines()
    results: list[str] = []
    seen: set[str] = set()
    pending_doc = ""
    for line in lines:
        if line.startswith("---[["):
            pending_doc = line.strip("-[] ").strip()
            continue
        if line.startswith("-- @"):
            continue
        if line.startswith("function "):
            sig = line[len("function "):].removesuffix(" end").strip()
            entry = f"{sig}  -- {pending_doc}" if pending_doc else sig
            pending_doc = ""
        else:
            entry = line.strip()
        if entry and term_lower in entry.lower() and entry not in seen:
            seen.add(entry)
            results.append(entry)
            if len(results) >= limit:
                break
    return results


def verify_vscript_api(search_term: str, refresh: bool = False, limit: int = 20) -> dict[str, Any]:
    """Look up real VScript functions/classes/constants in a per-build cache of 'script_help2'.

    The cache is built once per Dota 2 build (needs the game running with a map loaded);
    afterwards lookups work offline and do not touch the game console.
    """
    term = search_term.strip()
    if not term:
        return {"ok": False, "error": "Empty search_term."}

    build = _game_build()
    cache_file = VSCRIPT_CACHE_DIR / f"build_{build}.txt"
    source = "cache"
    if refresh or not cache_file.exists():
        built, err = _dump_vscript_api_to_cache(build)
        if built:
            cache_file, source = built, "live_dump"
        else:
            older = sorted(VSCRIPT_CACHE_DIR.glob("build_*.txt")) if VSCRIPT_CACHE_DIR.exists() else []
            if not older:
                return {"ok": False, "search_term": term, "error": err}
            cache_file, source = older[-1], f"stale_cache ({err})"

    matches = _search_vscript_cache(cache_file, term.lower(), max(1, min(limit, 50)))
    return {
        "ok": True,
        "search_term": term,
        "source": source,
        "build": cache_file.stem.removeprefix("build_"),
        "matches_count": len(matches),
        "matches": matches,
    }


def read_latest_console_log(
    tail_lines: int = 40, grep: str = "", only_errors: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """Read the tail of game/dota/console.log on disk (useful if NetCon is closed or game crashed).

    Known engine noise is hidden unless verbose=True; 'grep' keeps only lines containing that text.
    """
    log_path = _console_log_path()
    if not log_path:
        return {"ok": False, "error": "Dota 2 game_dir not found."}
    if not log_path.exists():
        return {
            "ok": False,
            "error": f"No console.log found at {log_path}. Add '-condebug' to Dota 2 launch options to enable disk logging.",
        }

    try:
        # Only the last 1 MB is read: console.log grows to many MB per session.
        size = log_path.stat().st_size
        with log_path.open("rb") as f:
            f.seek(max(0, size - 1024 * 1024))
            text = f.read().decode("utf-8", errors="replace")
        all_lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        kept, errors, hidden = _filter_console_lines(all_lines, verbose=verbose)
        if grep:
            kept = [l for l in kept if grep.lower() in l.lower()]
        n = max(5, min(tail_lines, 200))
        tail = (errors if only_errors else kept)[-n:]
        return {
            "ok": True,
            "noise_lines_hidden": hidden,
            "errors_and_warnings": errors[-20:] if not only_errors else [],
            "tail": tail,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
