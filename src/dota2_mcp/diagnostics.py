"""Module 6: MCP self-diagnostics, automatic Decompiler CLI downloader, and bug logger."""

from __future__ import annotations

import argparse
import datetime
import io
import json
import zipfile
from typing import Any

try:
    import requests
except ImportError:
    requests = None

from .config import BIN_DIR, BUG_LOG_PATH, CONFIG
from .netcon_bridge import check_netcon_open
from .vpk_explorer import search_dota_assets


VRF_RELEASES_API = "https://api.github.com/repos/ValveResourceFormat/ValveResourceFormat/releases/latest"


def ensure_decompiler_binary() -> dict[str, Any]:
    """Download latest ValveResourceFormat CLI (cli-windows-x64.zip) into bin/ if not present."""
    if CONFIG.decompiler_exe.exists():
        return {"ok": True, "status": "already_installed", "path": str(CONFIG.decompiler_exe)}

    if requests is None:
        return {"ok": False, "error": "Python library 'requests' is not installed."}

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(VRF_RELEASES_API, timeout=15)
        resp.raise_for_status()
        release_data = resp.json()
        assets = release_data.get("assets", [])

        download_url = None
        for asset in assets:
            name = asset.get("name", "").lower()
            if "cli-windows-x64.zip" in name or ("decompiler" in name and "windows-x64" in name):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            return {
                "ok": False,
                "error": "Could not find cli-windows-x64.zip in latest ValveResourceFormat release.",
            }

        zip_resp = requests.get(download_url, timeout=60)
        zip_resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            zf.extractall(BIN_DIR)

        # Normalize executable name if needed
        extracted_files = [p.name for p in BIN_DIR.iterdir()]
        return {
            "ok": CONFIG.decompiler_exe.exists(),
            "status": "downloaded",
            "release_tag": release_data.get("tag_name"),
            "extracted_files": extracted_files,
            "path": str(CONFIG.decompiler_exe),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_mcp_self_test(auto_download_decompiler: bool = True) -> dict[str, Any]:
    """Run comprehensive self-test of Dota 2 paths, VPK reading, Source 2 compilers, and NetCon."""
    decompiler_status: dict[str, Any] = {"checked": False}
    if auto_download_decompiler and not CONFIG.decompiler_exe.exists():
        decompiler_status = ensure_decompiler_binary()

    cfg_summary = CONFIG.summary()
    vpk_test = {"ok": False}
    if cfg_summary["pak01_dir_vpk_exists"]:
        res = search_dota_assets("pudge.vmdl", asset_type="model", limit=3)
        vpk_test = {
            "ok": res.get("ok", False) and res.get("count", 0) > 0,
            "sample_matches": res.get("results", []),
        }

    netcon_listening = check_netcon_open()

    all_ready = (
        cfg_summary["pak01_dir_vpk_exists"]
        and cfg_summary["dmxconvert_exists"]
        and cfg_summary["resourcecompiler_exists"]
        and vpk_test["ok"]
    )

    return {
        "ok": all_ready,
        "config": cfg_summary,
        "decompiler_bootstrap": decompiler_status,
        "vpk_index_test": vpk_test,
        "netcon_port_29000_open": netcon_listening,
        "ready_for_custom_game_creation": all_ready,
    }


def log_bug_report(
    component: str,
    symptom: str,
    root_cause: str,
    fix_applied: str,
    prevention_rule: str,
) -> dict[str, Any]:
    """Append a structured bug report and prevention rule to docs/BUG_LOG.md."""
    BUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"\n### [{now_str}] Компонент: `{component}`\n"
        f"- **Симптом / Ошибка:** {symptom}\n"
        f"- **Корневая причина:** {root_cause}\n"
        f"- **Примененное решение:** {fix_applied}\n"
        f"- **Правило предотвращения:** {prevention_rule}\n"
    )

    with open(BUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    return {
        "ok": True,
        "bug_log_path": str(BUG_LOG_PATH),
        "timestamp": now_str,
        "component": component,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dota 2 MCP Diagnostics & Bootstrap")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Download Decompiler CLI and run full environment self-test.",
    )
    args = parser.parse_args()
    result = run_mcp_self_test(auto_download_decompiler=args.bootstrap)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
