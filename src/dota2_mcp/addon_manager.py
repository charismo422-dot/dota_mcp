"""Module 3: Addon scaffolding, KeyValues syntax validation, automatic Precache sync, and localization."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

try:
    import vdf
except ImportError:
    vdf = None

from .config import CONFIG
from .vpk_explorer import asset_exists_in_vpk_or_addon


ASSET_REGEX = re.compile(
    r'["\']([a-zA-Z0-9_/-]+(?:/[a-zA-Z0-9_.-]+)+\.(?:vmdl|vpcf|vsndevts))["\']'
)


def create_or_configure_addon(
    addon_name: str,
    maps: list[str],
    max_players: int = 10,
    team_count: int = 2,
) -> dict[str, Any]:
    """Create a new addon from addon_template (if missing) and configure addoninfo.txt."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir or not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}

    game_addon = CONFIG.game_addons_dir / addon_name
    content_addon = CONFIG.content_addons_dir / addon_name

    template_game = CONFIG.game_addons_dir / "addon_template"
    template_content = CONFIG.content_addons_dir / "addon_template"

    created_new = False
    if not game_addon.exists():
        if template_game.exists():
            shutil.copytree(template_game, game_addon)
        else:
            (game_addon / "scripts" / "vscripts").mkdir(parents=True, exist_ok=True)
            (game_addon / "scripts" / "npc").mkdir(parents=True, exist_ok=True)
            (game_addon / "resource").mkdir(parents=True, exist_ok=True)
        created_new = True

    if not content_addon.exists():
        if template_content.exists():
            shutil.copytree(template_content, content_addon)
        else:
            (content_addon / "maps").mkdir(parents=True, exist_ok=True)
            (content_addon / "panorama" / "layout" / "custom_game").mkdir(
                parents=True, exist_ok=True
            )
        created_new = True

    # Ensure standard NPC KV files exist
    npc_dir = game_addon / "scripts" / "npc"
    npc_dir.mkdir(parents=True, exist_ok=True)
    default_kv_roots = {
        "npc_abilities_custom.txt": "DOTAAbilities",
        "npc_units_custom.txt": "DOTAUnits",
        "npc_heroes_custom.txt": "DOTAHeroes",
        "npc_items_custom.txt": "DOTAAbilities",
    }
    for fname, root_key in default_kv_roots.items():
        fpath = npc_dir / fname
        if not fpath.exists():
            fpath.write_text(f'"{root_key}"\n{{\n\t"Version"\t"1"\n}}\n', encoding="utf-8")

    # Configure addoninfo.txt
    addoninfo_path = game_addon / "addoninfo.txt"
    maps_str = " ".join(maps) if maps else "template_map"
    map_blocks = "\n".join(
        f'\t"{m}"\n\t{{\n\t\t"MaxPlayers"\t"{max_players}"\n\t}}' for m in (maps or ["template_map"])
    )
    addoninfo_content = (
        '"AddonInfo"\n'
        "{\n"
        f'\t"TeamCount"\t\t"{team_count}"\n'
        f'\t"maps"\t\t\t"{maps_str}"\n'
        '\t"IsPlayable"\t"1"\n'
        '\t"Default_Keys"\n\t{\n\t}\n'
        f"{map_blocks}\n"
        "}\n"
    )
    addoninfo_path.write_text(addoninfo_content, encoding="utf-8")

    return {
        "ok": True,
        "addon_name": addon_name,
        "created_new": created_new,
        "game_addon_path": str(game_addon),
        "content_addon_path": str(content_addon),
        "addoninfo_path": str(addoninfo_path),
        "maps": maps,
    }


def validate_and_sync_precache(addon_name: str) -> dict[str, Any]:
    """Validate KV syntax, check all referenced assets in VPK/addon, and sync Precache in addon_game_mode.lua."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}

    game_addon = CONFIG.game_addons_dir / addon_name
    if not game_addon.exists():
        return {"ok": False, "error": f"Addon '{addon_name}' does not exist at {game_addon}"}

    kv_errors: list[dict[str, str]] = []
    npc_dir = game_addon / "scripts" / "npc"
    if npc_dir.exists():
        for kv_file in sorted(npc_dir.rglob("*.txt")) + sorted(npc_dir.rglob("*.kv")):
            try:
                text = kv_file.read_text(encoding="utf-8", errors="replace")
                vdf.loads(text)
            except Exception as exc:
                kv_errors.append({"file": str(kv_file.relative_to(game_addon)), "error": str(exc)})

    # Scan all .lua, .txt, .kv files for .vmdl, .vpcf, .vsndevts references
    discovered_assets: set[str] = set()
    scripts_dir = game_addon / "scripts"
    if scripts_dir.exists():
        for src_file in list(scripts_dir.rglob("*.lua")) + list(scripts_dir.rglob("*.txt")):
            text = src_file.read_text(encoding="utf-8", errors="replace")
            for match in ASSET_REGEX.findall(text):
                discovered_assets.add(match)

    missing_assets: list[str] = []
    valid_assets: list[str] = []
    for asset in sorted(discovered_assets):
        if asset_exists_in_vpk_or_addon(asset, addon_name=addon_name):
            valid_assets.append(asset)
        else:
            missing_assets.append(asset)

    # Generate auto_precache.lua and hook into addon_game_mode.lua
    vscripts_dir = game_addon / "scripts" / "vscripts"
    vscripts_dir.mkdir(parents=True, exist_ok=True)
    auto_precache_file = vscripts_dir / "auto_precache.lua"

    precache_lines = [
        "-- Auto-generated by dota2-workshop-mcp (validate_and_sync_precache)",
        "return function(context)",
    ]
    for asset in valid_assets:
        if asset.endswith(".vmdl"):
            rtype = "model"
        elif asset.endswith(".vpcf"):
            rtype = "particle"
        elif asset.endswith(".vsndevts"):
            rtype = "soundfile"
        else:
            continue
        precache_lines.append(f'    PrecacheResource("{rtype}", "{asset}", context)')
    precache_lines.append("end\n")
    auto_precache_file.write_text("\n".join(precache_lines), encoding="utf-8")

    # Ensure addon_game_mode.lua calls require("auto_precache")(context) inside Precache(context)
    game_mode_lua = vscripts_dir / "addon_game_mode.lua"
    if game_mode_lua.exists():
        gm_text = game_mode_lua.read_text(encoding="utf-8", errors="replace")
        if "auto_precache" not in gm_text and "function Precache(" in gm_text:
            gm_text = re.sub(
                r"(function\s+Precache\s*\(\s*context\s*\))",
                r'\1\n\tpcall(function() require("auto_precache")(context) end)',
                gm_text,
                count=1,
            )
            game_mode_lua.write_text(gm_text, encoding="utf-8")

    return {
        "ok": len(kv_errors) == 0 and len(missing_assets) == 0,
        "kv_syntax_errors": kv_errors,
        "valid_assets_precached": len(valid_assets),
        "missing_or_hallucinated_assets": missing_assets,
        "auto_precache_file": str(auto_precache_file),
    }


def upsert_localization(
    addon_name: str, language: str, tokens: dict[str, str]
) -> dict[str, Any]:
    """Create or update game/dota_addons/<addon>/resource/addon_<language>.txt with UTF-8 Tokens."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}

    res_dir = CONFIG.game_addons_dir / addon_name / "resource"
    res_dir.mkdir(parents=True, exist_ok=True)
    lang_clean = language.lower().strip()
    loc_file = res_dir / f"addon_{lang_clean}.txt"

    existing_tokens: dict[str, str] = {"Language": lang_clean.capitalize()}
    if loc_file.exists():
        for enc in ("utf-8", "utf-16", "utf-16-le"):
            try:
                raw = loc_file.read_text(encoding=enc)
                parsed = vdf.loads(raw)
                lang_root = parsed.get("lang") or parsed.get("Lang") or {}
                tok_block = lang_root.get("Tokens") or lang_root.get("tokens") or {}
                if isinstance(tok_block, dict):
                    existing_tokens.update(tok_block)
                break
            except Exception:
                continue

    existing_tokens.update(tokens)

    lines = [
        '"lang"',
        "{",
        f'\t"Language"\t\t"{lang_clean.capitalize()}"',
        '\t"Tokens"',
        "\t{",
    ]
    for k, v in existing_tokens.items():
        if k == "Language":
            continue
        safe_v = str(v).replace('"', '\\"')
        lines.append(f'\t\t"{k}"\t\t"{safe_v}"')
    lines.extend(["\t}", "}", ""])

    loc_file.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "localization_file": str(loc_file),
        "updated_keys_count": len(tokens),
        "total_keys_count": len(existing_tokens),
    }
