"""Module 3: Addon scaffolding, KeyValues syntax validation, automatic Precache sync, and localization."""

from __future__ import annotations

import re
import shutil
import subprocess
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
    """Create a new addon from addon_template (if missing) and configure addoninfo.txt without clobbering existing keys."""
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

    # Configure addoninfo.txt while preserving any existing custom keys
    addoninfo_path = game_addon / "addoninfo.txt"
    effective_maps = maps if maps else ["template_map"]
    maps_str = " ".join(effective_maps)

    addon_dict: dict[str, Any] = {}
    if addoninfo_path.exists() and vdf is not None:
        try:
            raw_info = addoninfo_path.read_text(encoding="utf-8", errors="replace")
            parsed = vdf.loads(raw_info)
            root_val = parsed.get("AddonInfo") or parsed.get("addoninfo")
            if isinstance(root_val, dict):
                addon_dict = dict(root_val)
        except Exception:
            addon_dict = {}

    addon_dict["TeamCount"] = str(team_count)
    addon_dict["maps"] = maps_str
    addon_dict["IsPlayable"] = addon_dict.get("IsPlayable", "1")
    if "Default_Keys" not in addon_dict:
        addon_dict["Default_Keys"] = {}

    for m in effective_maps:
        existing_map_cfg = addon_dict.get(m)
        if isinstance(existing_map_cfg, dict):
            existing_map_cfg["MaxPlayers"] = str(max_players)
        else:
            addon_dict[m] = {"MaxPlayers": str(max_players)}

    if vdf is not None:
        addoninfo_content = vdf.dumps({"AddonInfo": addon_dict}, pretty=True)
    else:
        map_blocks = "\n".join(
            f'\t"{m}"\n\t{{\n\t\t"MaxPlayers"\t"{max_players}"\n\t}}'
            for m in effective_maps
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
        "maps": effective_maps,
        "directory_routing": get_addon_paths(addon_name),
    }


def get_addon_paths(addon_name: str) -> dict[str, Any]:
    """Return exact canonical paths for game/ (runtime scripts/KV) vs content/ (source assets requiring compilation)."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir or not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}

    game_base = CONFIG.game_addons_dir / addon_name
    content_base = CONFIG.content_addons_dir / addon_name

    return {
        "ok": True,
        "addon_name": addon_name,
        "GAME_RUNTIME_DIRS (NO resourcecompiler needed)": {
            "root": str(game_base),
            "vscripts_lua": str(game_base / "scripts" / "vscripts"),
            "npc_keyvalues": str(game_base / "scripts" / "npc"),
            "localization": str(game_base / "resource"),
            "compiled_spellicons_output": str(
                game_base / "panorama" / "images" / "spellicons"
            ),
            "compiled_itemicons_output": str(
                game_base / "panorama" / "images" / "items"
            ),
        },
        "CONTENT_SOURCE_DIRS (MUST compile via resourcecompiler.exe -> generates _c in game/)": {
            "root": str(content_base),
            "maps_vmap": str(content_base / "maps"),
            "panorama_xml_layout": str(
                content_base / "panorama" / "layout" / "custom_game"
            ),
            "panorama_js_scripts": str(
                content_base / "panorama" / "scripts" / "custom_game"
            ),
            "panorama_css_styles": str(
                content_base / "panorama" / "styles" / "custom_game"
            ),
            "custom_ability_icons_png_src": str(
                content_base / "panorama" / "images" / "spellicons"
            ),
            "custom_item_icons_png_src": str(
                content_base / "panorama" / "images" / "items"
            ),
            "sounds_src": str(content_base / "sounds"),
            "soundevents_src": str(content_base / "soundevents"),
            "materials_src": str(content_base / "materials"),
            "particles_src": str(content_base / "particles"),
        },
    }


def validate_and_sync_precache(addon_name: str) -> dict[str, Any]:
    """Validate KV syntax, detect misplaced files between game/ and content/, auto-compile custom icons, verify VPK assets, and sync Precache."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir or not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}

    game_addon = CONFIG.game_addons_dir / addon_name
    content_addon = CONFIG.content_addons_dir / addon_name
    if not game_addon.exists():
        return {"ok": False, "error": f"Addon '{addon_name}' does not exist at {game_addon}"}

    # 1. Detect misplaced files (e.g. raw .png/.xml/.css/.js/.vmap in game/, or .lua in content/)
    misplaced_files: list[dict[str, str]] = []
    legacy_flash3 = game_addon / "resource" / "flash3"
    if legacy_flash3.exists():
        misplaced_files.append(
            {
                "path": str(legacy_flash3),
                "issue": "OBSOLETE Source 1 'resource/flash3' directory detected in game/! Dota 2 7.41+ ignores flash3.",
                "fix": f"Move all .png icons to {content_addon / 'panorama/images/spellicons'} (or items/) and compile via resourcecompiler.exe.",
            }
        )

    for bad_ext, dest_hint in (
        ("*.xml", "content/.../panorama/layout/custom_game/"),
        ("*.css", "content/.../panorama/styles/custom_game/"),
        ("*.js", "content/.../panorama/scripts/custom_game/"),
        ("*.vmap", "content/.../maps/"),
        ("*.png", "content/.../panorama/images/spellicons/ (or items/)"),
    ):
        for f in game_addon.rglob(bad_ext):
            if f.name in ("addon_icon.png",):
                continue
            misplaced_files.append(
                {
                    "path": str(f.relative_to(game_addon)),
                    "issue": f"Raw source file '{f.name}' placed inside game/ directory. Source 2 only reads compiled (*_c) assets in game/.",
                    "fix": f"Move to {dest_hint} inside content/dota_addons/{addon_name}/ and run compile_addon_resource.",
                }
            )

    if content_addon.exists():
        for lua_f in content_addon.rglob("*.lua"):
            misplaced_files.append(
                {
                    "path": str(lua_f.relative_to(content_addon)),
                    "issue": f"Lua script '{lua_f.name}' placed in content/ instead of game/.",
                    "fix": f"Move to game/dota_addons/{addon_name}/scripts/vscripts/.",
                }
            )

    # 2. Auto-compile any raw .png icons in content/.../panorama/images/ that lack a compiled _png.vtex_c in game/
    auto_compiled_icons: list[str] = []
    icon_compile_errors: list[str] = []
    content_images_dir = content_addon / "panorama" / "images"
    if (
        content_images_dir.exists()
        and CONFIG.resourcecompiler_exe
        and CONFIG.resourcecompiler_exe.exists()
    ):
        for png_file in content_images_dir.rglob("*.png"):
            rel_png = png_file.relative_to(content_addon)
            expected_vtex = (
                game_addon
                / rel_png.parent
                / f"{png_file.stem}_png.vtex_c"
            )
            if not expected_vtex.exists():
                proc = subprocess.run(
                    [str(CONFIG.resourcecompiler_exe), "-i", str(png_file)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                if proc.returncode == 0 and expected_vtex.exists():
                    auto_compiled_icons.append(str(rel_png))
                else:
                    icon_compile_errors.append(
                        f"Failed to compile {rel_png}: {proc.stdout} {proc.stderr}"
                    )

    # 3. Validate KV syntax and check AbilityTextureName in items/abilities
    kv_errors: list[dict[str, str]] = []
    icon_warnings: list[str] = []
    npc_dir = game_addon / "scripts" / "npc"
    if npc_dir.exists():
        for kv_file in sorted(npc_dir.rglob("*.txt")) + sorted(npc_dir.rglob("*.kv")):
            try:
                text = kv_file.read_text(encoding="utf-8", errors="replace")
                parsed_kv = vdf.loads(text)
                root_block = next(iter(parsed_kv.values())) if parsed_kv else {}
                if isinstance(root_block, dict):
                    is_item_file = "item" in kv_file.name.lower()
                    for entry_name, entry_data in root_block.items():
                        if not isinstance(entry_data, dict):
                            continue
                        tex_name = entry_data.get("AbilityTextureName")
                        if tex_name and is_item_file:
                            clean_tex = tex_name.removeprefix("item_")
                            custom_item_png = (
                                content_addon
                                / "panorama"
                                / "images"
                                / "items"
                                / f"{clean_tex}.png"
                            )
                            if custom_item_png.exists() and not tex_name.startswith("item_"):
                                icon_warnings.append(
                                    f"In {kv_file.name} -> '{entry_name}': AbilityTextureName is '{tex_name}', "
                                    f"but for items with custom PNG '{custom_item_png.name}' in panorama/images/items/, "
                                    f"Dota 2 requires 'AbilityTextureName' to be 'item_{clean_tex}'."
                                )
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

    # Generate auto_precache.lua and hook into addon_game_mode.lua with visible xpcall error logging
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

    # Ensure addon_game_mode.lua calls require("auto_precache")(context) with xpcall inside Precache(context)
    game_mode_lua = vscripts_dir / "addon_game_mode.lua"
    xpcall_line = '\txpcall(function() require("auto_precache")(context) end, function(err) print("[MCP Precache Error] " .. tostring(err)) end)'
    if game_mode_lua.exists():
        gm_text = game_mode_lua.read_text(encoding="utf-8", errors="replace")
        if "auto_precache" not in gm_text and "function Precache(" in gm_text:
            gm_text = re.sub(
                r"(function\s+Precache\s*\(\s*context\s*\))",
                rf"\1\n{xpcall_line}",
                gm_text,
                count=1,
            )
            game_mode_lua.write_text(gm_text, encoding="utf-8")
        elif 'pcall(function() require("auto_precache")(context) end)' in gm_text:
            gm_text = gm_text.replace(
                'pcall(function() require("auto_precache")(context) end)',
                xpcall_line.lstrip(),
            )
            game_mode_lua.write_text(gm_text, encoding="utf-8")

    return {
        "ok": (
            len(kv_errors) == 0
            and len(missing_assets) == 0
            and len(misplaced_files) == 0
            and len(icon_compile_errors) == 0
        ),
        "kv_syntax_errors": kv_errors,
        "misplaced_files_game_vs_content": misplaced_files,
        "auto_compiled_icons": auto_compiled_icons,
        "icon_compile_errors": icon_compile_errors,
        "icon_naming_warnings": icon_warnings,
        "valid_assets_precached": len(valid_assets),
        "missing_or_hallucinated_assets": missing_assets,
        "auto_precache_file": str(auto_precache_file),
    }


def upsert_localization(
    addon_name: str, language: str, tokens: dict[str, str]
) -> dict[str, Any]:
    """Create or update game/dota_addons/<addon>/resource/addon_<language>.txt."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}

    res_dir = CONFIG.game_addons_dir / addon_name / "resource"
    res_dir.mkdir(parents=True, exist_ok=True)
    lang_clean = language.lower().strip()
    loc_file = res_dir / f"addon_{lang_clean}.txt"

    existing_tokens: dict[str, str] = {"Language": lang_clean.capitalize()}
    target_encoding = "utf-8-sig"
    if loc_file.exists():
        raw_head = loc_file.read_bytes()[:4]
        if raw_head.startswith((b"\xff\xfe", b"\xfe\xff")):
            target_encoding = "utf-16"
        for enc in ("utf-16", "utf-8-sig", "utf-8", "utf-16-le"):
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

    loc_file.write_text("\n".join(lines), encoding=target_encoding)
    return {
        "ok": True,
        "localization_file": str(loc_file),
        "encoding": target_encoding,
        "updated_keys_count": len(tokens),
        "total_keys_count": len(existing_tokens),
    }
