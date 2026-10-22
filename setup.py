"""Idempotent Windows setup & agent configuration script for dota_mcp."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
SKILL_SRC_DIR = REPO_ROOT / ".agents" / "skills" / "dota2-custom-game-dev"
CLAUDE_SKILL_DST_DIR = REPO_ROOT / ".claude" / "skills" / "dota2-custom-game-dev"
CLAUDE_MCP_JSON = REPO_ROOT / ".mcp.json"


def _fail(title: str, details: list[str], code: int = 1) -> None:
    print(f"\n[ERROR] {title}", file=sys.stderr)
    for line in details:
        print(f"  - {line}", file=sys.stderr)
    sys.exit(code)


def check_python_and_os() -> None:
    print("[1/6] Checking OS and Python version...")
    if platform.system() != "Windows":
        _fail(
            f"Unsupported operating system: {platform.system()}",
            [
                "Dota 2 Workshop Tools (dmxconvert.exe, resourcecompiler.exe) only run on Windows 10/11 (64-bit).",
            ],
        )
    if sys.version_info < (3, 10):
        _fail(
            f"Python 3.10+ is required (detected Python {sys.version.split()[0]}).",
            [
                "Install Python 3.10 or newer from https://www.python.org/downloads/windows/ and re-run setup.py.",
            ],
        )
    print(f"  OK: Windows ({platform.release()}) | Python {sys.version.split()[0]}")


def ensure_venv_and_deps(venv_dir: Path) -> Path:
    print("[2/6] Setting up virtual environment (.venv) and Python dependencies...")
    venv_python = venv_dir / "Scripts" / "python.exe"
    if not venv_python.exists():
        print(f"  Creating virtual environment at {venv_dir}...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    else:
        print(f"  Reusing existing virtual environment at {venv_dir}.")

    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        check=True,
    )
    print("  OK: Dependencies installed (mcp>=2.3.0,<3.0.0, vpk, vdf, requests).")
    return venv_python


def check_dota_and_workshop_tools(
    venv_python: Path, dota_path_override: Optional[str]
) -> dict[str, Any]:
    print("[3/6] Locating Dota 2 and verifying Workshop Tools DLC...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    if dota_path_override is not None:
        env["DOTA2_PATH"] = dota_path_override

    probe_code = (
        "import json, os; "
        "from pathlib import Path; "
        "from src.dota2_mcp.config import DotaConfig, find_dota2_root; "
        "override = os.environ.get('DOTA2_PATH'); "
        "root = Path(override) if override is not None else find_dota2_root(); "
        "cfg = DotaConfig(dota_root=root if (root and root.exists()) else None); "
        "summary = cfg.summary(); "
        "summary['checked_override'] = override; "
        "summary['template_addon_exists'] = bool(cfg.content_addons_dir and (cfg.content_addons_dir / 'addon_template').exists()); "
        "print(json.dumps(summary))"
    )
    proc = subprocess.run(
        [str(venv_python), "-c", probe_code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(proc.stdout.strip())

    dota_root = info.get("dota_root")
    checked = info.get("checked_override") or dota_root or "<not found in Steam libraryfolders.vdf>"
    if (
        info.get("checked_override")
        and (not dota_root or not Path(info["checked_override"]).exists())
    ) or not dota_root or not Path(dota_root).exists() or not info.get("pak01_dir_vpk_exists"):
        _fail(
            "Dota 2 installation ('dota 2 beta') was not found.",
            [
                f"Checked path: {checked}",
                "Make sure Dota 2 is installed via Steam.",
                "If Dota 2 is in a custom folder, pass --dota-path \"<path to dota 2 beta>\" or set DOTA2_PATH.",
            ],
        )

    missing_tools: list[str] = []
    if not info.get("dmxconvert_exists"):
        missing_tools.append("game/bin/win64/dmxconvert.exe")
    if not info.get("resourcecompiler_exists"):
        missing_tools.append("game/bin/win64/resourcecompiler.exe")
    if not info.get("template_addon_exists"):
        missing_tools.append("content/dota_addons/addon_template")

    if missing_tools:
        _fail(
            "Dota 2 was found, but Dota 2 Workshop Tools DLC is not installed.",
            [
                f"Dota 2 directory: {dota_root}",
                f"Missing Workshop Tools files: {', '.join(missing_tools)}",
                "How to fix: Open Steam -> Library -> Right-click Dota 2 -> Properties -> DLC -> check 'Dota 2 Workshop Tools DLC' and wait for the download to finish.",
            ],
        )

    print(f"  OK: Dota 2 & Workshop Tools verified at: {dota_root}")
    return info


def ensure_decompiler(venv_python: Path) -> None:
    print("[4/6] Ensuring Source2Viewer-CLI.exe (ValveResourceFormat) in bin/...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    code = (
        "import json, sys; "
        "from src.dota2_mcp.diagnostics import ensure_decompiler_binary; "
        "res = ensure_decompiler_binary(); "
        "print(json.dumps(res)); "
        "sys.exit(0 if res.get('ok') else 1)"
    )
    proc = subprocess.run(
        [str(venv_python), "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        _fail(
            "Failed to download or verify Source2Viewer-CLI.exe in bin/.",
            [proc.stdout.strip() or proc.stderr.strip()],
        )
    res = json.loads(proc.stdout.strip())
    print(f"  OK: {res.get('status')} -> {res.get('path')}")


def _merge_mcp_server_entry(config_path: Path, server_entry: dict[str, Any]) -> None:
    """Safely merge 'dota2-workshop-mcp' into mcpServers without overwriting other servers."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            raw = config_path.read_text(encoding="utf-8-sig").strip()
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception as exc:
            backup = config_path.with_suffix(".json.bak")
            shutil.copy2(config_path, backup)
            print(f"  [WARN] Could not parse existing {config_path} ({exc}); backed up to {backup}")
            data = {}

    mcp_servers = data.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
        data["mcpServers"] = mcp_servers

    mcp_servers["dota2-workshop-mcp"] = server_entry
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def configure_agents(venv_python: Path, home_dir: Path, dota_root: str) -> None:
    print("[5/6] Generating MCP configurations and syncing agent skills...")
    server_entry: dict[str, Any] = {
        "command": str(venv_python.resolve()),
        "args": ["-m", "src.dota2_mcp.server"],
        "cwd": str(REPO_ROOT.resolve()),
        "env": {
            "PYTHONPATH": str(REPO_ROOT.resolve()),
            "DOTA2_PATH": dota_root,
        },
    }

    # 1. Antigravity MCP configs (~/.gemini/antigravity/mcp_config.json and ~/.gemini/config/mcp_config.json)
    ag_paths = [
        home_dir / ".gemini" / "antigravity" / "mcp_config.json",
        home_dir / ".gemini" / "config" / "mcp_config.json",
    ]
    resolved_seen: set[Path] = set()
    for cfg_path in ag_paths:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            real_target = cfg_path.resolve()
        except OSError:
            real_target = cfg_path
        if real_target in resolved_seen and cfg_path.exists():
            print(f"  OK: Antigravity config (linked): {cfg_path}")
            continue
        _merge_mcp_server_entry(cfg_path, server_entry)
        resolved_seen.add(real_target)
        print(f"  OK: Antigravity MCP config updated: {cfg_path}")

    # 2. Claude Code project config (.mcp.json in repo root)
    _merge_mcp_server_entry(CLAUDE_MCP_JSON, server_entry)
    print(f"  OK: Claude Code MCP config updated: {CLAUDE_MCP_JSON}")

    # 3. Copy skill to .claude/skills/dota2-custom-game-dev
    if SKILL_SRC_DIR.exists():
        if CLAUDE_SKILL_DST_DIR.exists():
            shutil.rmtree(CLAUDE_SKILL_DST_DIR)
        CLAUDE_SKILL_DST_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL_SRC_DIR, CLAUDE_SKILL_DST_DIR)
        print(f"  OK: Skill copied to {CLAUDE_SKILL_DST_DIR}")


def run_final_self_test(venv_python: Path, dota_root: str) -> None:
    print("[6/6] Running MCP server self-test (run_mcp_self_test)...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["DOTA2_PATH"] = dota_root

    proc = subprocess.run(
        [str(venv_python), "-m", "src.dota2_mcp.diagnostics", "--bootstrap"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        _fail("MCP self-test failed to execute.", [proc.stderr.strip() or proc.stdout.strip()])

    result = json.loads(proc.stdout.strip())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("ok"):
        _fail("MCP self-test reported readiness=false.", ["Check the JSON output above."])
    print("\n[SUCCESS] dota_mcp is installed, configured, and ready for use!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotent installer and MCP configurator for dota_mcp."
    )
    parser.add_argument(
        "--home",
        type=str,
        default=None,
        help="Override target user home directory for Antigravity MCP config files (useful for isolated testing).",
    )
    parser.add_argument(
        "--dota-path",
        type=str,
        default=None,
        help="Explicit path to 'dota 2 beta' directory (overrides automatic Steam discovery).",
    )
    args = parser.parse_args()

    target_home = Path(args.home).resolve() if args.home else Path.home()
    venv_dir = REPO_ROOT / ".venv"

    check_python_and_os()
    venv_python = ensure_venv_and_deps(venv_dir)
    dota_info = check_dota_and_workshop_tools(venv_python, args.dota_path)
    ensure_decompiler(venv_python)
    configure_agents(venv_python, target_home, str(dota_info["dota_root"]))
    run_final_self_test(venv_python, str(dota_info["dota_root"]))


if __name__ == "__main__":
    main()
