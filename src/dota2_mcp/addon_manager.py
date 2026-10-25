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

    # Remove readonly_tools_asset_info.bin if copied from addon_template
    readonly_bin = game_addon / "readonly_tools_asset_info.bin"
    if readonly_bin.exists():
        try:
            readonly_bin.unlink()
        except OSError:
            pass

    # Remove obsolete Source 1 resource/flash3 copied from addon_template (only on fresh creation)
    flash3_dir = game_addon / "resource" / "flash3"
    if created_new and flash3_dir.exists():
        shutil.rmtree(flash3_dir, ignore_errors=True)

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

    # Configure addoninfo.txt while preserving any existing custom keys.
    # CRITICAL: Remove "IsTemplate" (which hides addon_template/hero_demo/npx_2019/tutorial_* from Workshop Tools UI)
    # and force "IsPlayable" = "1". Also handle KV3 header if addon was created via Workshop Tools button.
    addoninfo_path = game_addon / "addoninfo.txt"
    effective_maps = maps if maps else ["template_map"]
    maps_str = " ".join(effective_maps)

    addon_dict: dict[str, Any] = {}
    if addoninfo_path.exists() and vdf is not None:
        try:
            raw_info = addoninfo_path.read_text(encoding="utf-8", errors="replace")
            if not raw_info.lstrip().startswith("<!-- kv3"):
                parsed = vdf.loads(raw_info)
                root_val = parsed.get("AddonInfo") or parsed.get("addoninfo")
                if isinstance(root_val, dict):
                    addon_dict = dict(root_val)
        except Exception:
            addon_dict = {}

    # Strip template/hidden flags inherited from addon_template
    addon_dict.pop("IsTemplate", None)
    addon_dict.pop("istemplate", None)
    addon_dict.pop("HideInTools", None)

    addon_dict["TeamCount"] = str(team_count)
    addon_dict["maps"] = maps_str
    addon_dict["IsPlayable"] = "1"
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

    # 2. Auto-compile raw .png icons in content/.../panorama/images/ that lack an up-to-date _png.vtex_c in game/.
    # resourcecompiler has no compiler for a bare .png ("Failed to find compiler for file"); images are built
    # as dependencies of a Panorama layout. So a hidden layout referencing every icon is generated and compiled.
    auto_compiled_icons: list[str] = []
    icon_compile_errors: list[str] = []
    content_images_dir = content_addon / "panorama" / "images"
    if (
        content_images_dir.exists()
        and CONFIG.resourcecompiler_exe
        and CONFIG.resourcecompiler_exe.exists()
    ):
        all_pngs = sorted(content_images_dir.rglob("*.png"))

        def _vtex_for(png: Path) -> Path:
            return game_addon / png.relative_to(content_addon).parent / f"{png.stem}_png.vtex_c"

        stale = [
            p for p in all_pngs
            if not _vtex_for(p).exists() or _vtex_for(p).stat().st_mtime < p.stat().st_mtime
        ]
        if stale:
            layout_dir = content_addon / "panorama" / "layout" / "custom_game"
            layout_dir.mkdir(parents=True, exist_ok=True)
            icons_layout = layout_dir / "mcp_auto_icons.xml"
            image_tags = "\n".join(
                f'\t\t<Image src="file://{{images}}/{p.relative_to(content_images_dir).as_posix()}" />'
                for p in all_pngs
            )
            icons_layout.write_text(
                "<root>\n\t<!-- Auto-generated by dota2-workshop-mcp: never shown, only makes resourcecompiler build icons -->\n"
                f"\t<Panel>\n{image_tags}\n\t</Panel>\n</root>\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [str(CONFIG.resourcecompiler_exe), "-i", str(icons_layout)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            for png_file in stale:
                rel_png = png_file.relative_to(content_addon)
                vtex = _vtex_for(png_file)
                if vtex.exists() and vtex.stat().st_mtime >= png_file.stat().st_mtime:
                    auto_compiled_icons.append(str(rel_png))
                else:
                    icon_compile_errors.append(
                        f"Failed to compile {rel_png} via {icons_layout.name}: {proc.stdout[-800:]} {proc.stderr[-400:]}"
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

    sound_report = _resolve_sound_events(scripts_dir, content_addon)
    discovered_assets.update(sound_report.pop("soundfiles"))

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

    loc_report = _check_localization(game_addon, content_addon)

    return {
        "ok": (
            len(kv_errors) == 0
            and len(missing_assets) == 0
            and len(misplaced_files) == 0
            and len(icon_compile_errors) == 0
            and len(sound_report["unknown_sound_events"]) == 0
        ),
        "localization": loc_report,
        "kv_syntax_errors": kv_errors,
        "misplaced_files_game_vs_content": misplaced_files,
        "auto_compiled_icons": auto_compiled_icons,
        "icon_compile_errors": icon_compile_errors,
        "icon_naming_warnings": icon_warnings,
        "valid_assets_precached": len(valid_assets),
        "missing_or_hallucinated_assets": missing_assets,
        **sound_report,
        "auto_precache_file": str(auto_precache_file),
    }


def _read_loc_tokens(loc_file: Path) -> dict[str, str]:
    """Tokens of a resource/addon_<lang>.txt (UTF-16 or UTF-8, with or without BOM)."""
    raw = loc_file.read_bytes()
    # BOM decides first: decoding a UTF-8 file as UTF-16 "succeeds" with garbage and parses to nothing
    if raw.startswith(b"\xef\xbb\xbf"):
        encodings = ("utf-8-sig",)
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8", "utf-16-le")
    for enc in encodings:
        try:
            parsed = vdf.loads(raw.decode(enc))
        except Exception:
            continue
        lang_root = next((v for k, v in parsed.items() if k.lower() == "lang"), None)
        if isinstance(lang_root, dict):
            tok_block = next((v for k, v in lang_root.items() if k.lower() == "tokens"), {})
            return dict(tok_block) if isinstance(tok_block, dict) else {}
    return {}


# '#token' references: XML text="#x", JS $.Localize("#x"), Lua "#x_y" (needs '_' so panel ids/colors don't match)
LOC_XML_RE = re.compile(r'text\s*=\s*"#([A-Za-z_][A-Za-z0-9_]*)"')
# A literal followed by concatenation ("#prefix_" + x / "#prefix_" .. x) is a dynamic token prefix, not a token
LOC_JS_RE = re.compile(r'\$\.Localize\(\s*["\']#([A-Za-z_][A-Za-z0-9_]*)["\'](?!\s*\+)')
LOC_LUA_RE = re.compile(r'["\']#([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]*)["\'](?!\s*\.\.)')
# %value% in ability descriptions must name an AbilityValues key (%% is a literal percent sign)
TOOLTIP_VAR_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")
LINK_MODIFIER_RE = re.compile(r'LinkLuaModifier\(\s*["\'](\w+)["\']')


def _check_localization(game_addon: Path, content_addon: Path) -> dict[str, Any]:
    """Find untranslated names/tooltips, tokens missing in some language, unknown '#tokens' and bad %vars%."""
    res_dir = game_addon / "resource"
    langs: dict[str, dict[str, str]] = {}
    if res_dir.exists():
        for f in sorted(res_dir.glob("addon_*.txt")):
            langs[f.stem.removeprefix("addon_")] = _read_loc_tokens(f)
    all_tokens = {k.lower() for toks in langs.values() for k in toks}

    # Tokens the game will look up: names/descriptions of custom abilities, items, units, hero overrides
    required: set[str] = set()
    ability_values: dict[str, set[str]] = {}
    npc_dir = game_addon / "scripts" / "npc"
    for kv_name in ("npc_abilities_custom.txt", "npc_items_custom.txt", "npc_units_custom.txt", "npc_heroes_custom.txt"):
        kv_file = npc_dir / kv_name
        if not kv_file.exists():
            continue
        try:
            parsed = vdf.loads(kv_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        root_block = next(iter(parsed.values())) if parsed else {}
        if not isinstance(root_block, dict):
            continue
        for name, data in root_block.items():
            if not isinstance(data, dict):
                continue
            if kv_name in ("npc_abilities_custom.txt", "npc_items_custom.txt"):
                keys = set((data.get("AbilityValues") or {}).keys())
                for special in (data.get("AbilitySpecial") or {}).values():
                    if isinstance(special, dict):
                        keys.update(k for k in special if k not in ("var_type", "LinkedSpecialBonus"))
                ability_values[name.lower()] = {k.lower() for k in keys}
                if "HIDDEN" in str(data.get("AbilityBehavior", "")):
                    continue
                required.update({f"DOTA_Tooltip_ability_{name}", f"DOTA_Tooltip_ability_{name}_Description"})
            elif kv_name == "npc_heroes_custom.txt":
                required.add(data.get("override_hero") or name)
            else:
                required.add(name)

    # Lua modifiers that show an icon need a name and a description. Skipped: IsHidden returning true,
    # and thinker modifiers (CreateModifierThinker), which live on an invisible dummy unit.
    scripts_dir = game_addon / "scripts" / "vscripts"
    lua_texts = {f: f.read_text(encoding="utf-8", errors="replace") for f in scripts_dir.rglob("*.lua")} if scripts_dir.exists() else {}
    all_lua = "\n".join(lua_texts.values())
    for mod in set(LINK_MODIFIER_RE.findall(all_lua)):
        if re.search(rf"function\s+{mod}:IsHidden\(\)\s*return\s+true", all_lua) or re.search(
            rf"CreateModifierThinker\([^)]*[\"']{mod}[\"']", all_lua
        ):
            continue
        required.update({f"DOTA_Tooltip_{mod}", f"DOTA_Tooltip_{mod}_Description"})

    # '#tokens' referenced from Panorama and Lua
    referenced: dict[str, str] = {}
    panorama_dir = content_addon / "panorama"
    sources: list[tuple[Path, re.Pattern[str], str]] = []
    if panorama_dir.exists():
        sources += [(f, LOC_XML_RE, f.read_text(encoding="utf-8", errors="replace")) for f in panorama_dir.rglob("*.xml")]
        sources += [(f, LOC_JS_RE, f.read_text(encoding="utf-8", errors="replace")) for f in panorama_dir.rglob("*.js")]
    sources += [(f, LOC_LUA_RE, text) for f, text in lua_texts.items()]
    for f, pattern, text in sources:
        for tok in pattern.findall(text):
            referenced.setdefault(tok, f.name)

    untranslated = sorted(t for t in required if t.lower() not in all_tokens)
    unknown_refs = sorted(f"#{t} ({src})" for t, src in referenced.items() if t.lower() not in all_tokens)

    missing_in_language: dict[str, list[str]] = {}
    for lang, toks in langs.items():
        own = {k.lower() for k in toks}
        missing = sorted({k for other in langs.values() for k in other if k.lower() not in own})
        if missing:
            missing_in_language[lang] = missing

    bad_vars: list[str] = []
    for lang, toks in langs.items():
        for key, text in toks.items():
            m = re.match(r"DOTA_Tooltip_ability_(\w+?)_(Description|Lore|Note\d+)$", key, re.IGNORECASE)
            if not m or m.group(1).lower() not in ability_values:
                continue
            known = ability_values[m.group(1).lower()]
            for var in TOOLTIP_VAR_RE.findall(str(text)):
                if var.lower() not in known:
                    bad_vars.append(f"{lang}: {key} -> %{var}% (not in AbilityValues)")

    return {
        "languages": sorted(langs),
        "ok": not (untranslated or unknown_refs or missing_in_language or bad_vars or not langs),
        "untranslated_names": untranslated,
        "unknown_token_references": unknown_refs,
        "missing_in_language": missing_in_language,
        "bad_tooltip_variables": bad_vars,
    }


# String literal that looks like a sound event name: Hero_Pudge.Attack, MCP_Lab.Chime
SOUND_NAME_LITERAL_RE = re.compile(r'["\']([A-Za-z0-9_]+(?:\.[A-Za-z0-9_\-]+)+)["\']')
# Lua calls whose string arguments must be sound events
SOUND_CALL_RE = re.compile(
    r"\b(?:EmitSound\w*|EmitGlobalSound|EmitAnnouncerSound\w*|StartSoundEvent\w*|StopSound\w*|StopGlobalSound)\s*\(([^\n]*)"
)


def _resolve_sound_events(scripts_dir: Path, content_addon: Path) -> dict[str, Any]:
    """Find sound event names used in addon scripts/KV and map them to the .vsndevts files to precache.

    Addon events come from content/<addon>/soundevents/**/*.vsndevts, stock events from the cached
    VPK index (vpk_explorer.get_sound_event_index). Names passed to EmitSound*/StopSound* that exist
    in neither are reported as unknown (likely typos or hallucinated names).
    """
    from .vpk_explorer import get_sound_event_index, parse_vsndevts_event_names

    custom: dict[str, str] = {}
    sev_dir = content_addon / "soundevents"
    if sev_dir.exists():
        for f in sev_dir.rglob("*.vsndevts"):
            rel = f.relative_to(content_addon).as_posix()
            for name in parse_vsndevts_event_names(f.read_text(encoding="utf-8", errors="replace")):
                custom.setdefault(name.lower(), rel)

    try:
        stock = get_sound_event_index()["events"]
        index_error = ""
    except Exception as exc:
        stock, index_error = {}, str(exc)

    used: set[str] = set()
    in_calls: set[str] = set()
    if scripts_dir.exists():
        for src_file in list(scripts_dir.rglob("*.lua")) + list(scripts_dir.rglob("*.txt")):
            text = src_file.read_text(encoding="utf-8", errors="replace")
            used.update(SOUND_NAME_LITERAL_RE.findall(text))
            for args in SOUND_CALL_RE.findall(text):
                in_calls.update(SOUND_NAME_LITERAL_RE.findall(args))

    soundfiles: set[str] = set()
    resolved: dict[str, str] = {}
    for name in sorted(used | in_calls):
        low = name.lower()
        target = custom.get(low) or (stock.get(low) or {}).get("file")
        if target:
            soundfiles.add(target)
            resolved[name] = target
    unknown = sorted(n for n in in_calls if n not in resolved) if not index_error else []

    report: dict[str, Any] = {
        "soundfiles": soundfiles,
        "sound_events_resolved": len(resolved),
        "sound_files_from_events": sorted(soundfiles),
        "custom_sound_events": sorted(n for n, f in resolved.items() if custom.get(n.lower()) == f),
        "unknown_sound_events": unknown,
    }
    if index_error:
        report["sound_index_error"] = index_error
    return report


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
    # Verified on Windows: game/dota_addons/addon_template/resource/addon_english.txt
    # starts with b'\xff\xfe' (UTF-16 LE with BOM, i.e. Python encoding="utf-16").
    target_encoding = "utf-16"
    if loc_file.exists():
        raw_head = loc_file.read_bytes()[:4]
        if raw_head.startswith(b"\xef\xbb\xbf"):
            target_encoding = "utf-8-sig"
        elif raw_head.startswith((b"\xff\xfe", b"\xfe\xff")):
            target_encoding = "utf-16"
        existing_tokens.update(_read_loc_tokens(loc_file))

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
        # vdf unescapes \n and \" on read: escape them back so a round trip keeps one-line values
        safe_v = str(v).replace('"', '\\"').replace("\r\n", "\\n").replace("\n", "\\n")
        lines.append(f'\t\t"{k}"\t\t"{safe_v}"')
    lines.extend(["\t}", "}", ""])

    loc_file.write_text("\n".join(lines), encoding=target_encoding)

    # Tokens other languages have but this one does not (and vice versa): untranslated text in game
    own = {k.lower() for k in existing_tokens if k != "Language"}
    missing_here: set[str] = set()
    missing_elsewhere: dict[str, list[str]] = {}
    for other in sorted(res_dir.glob("addon_*.txt")):
        if other == loc_file:
            continue
        other_tokens = _read_loc_tokens(other)
        other_lower = {k.lower() for k in other_tokens}
        missing_here.update(k for k in other_tokens if k.lower() not in own)
        gap = sorted(k for k in tokens if k.lower() not in other_lower)
        if gap:
            missing_elsewhere[other.stem.removeprefix("addon_")] = gap
    result: dict[str, Any] = {
        "ok": True,
        "localization_file": str(loc_file),
        "encoding": target_encoding,
        "updated_keys_count": len(tokens),
        "total_keys_count": len(existing_tokens) - 1,
    }
    if missing_here:
        result["missing_in_this_language"] = sorted(missing_here)
    if missing_elsewhere:
        result["not_yet_in_other_languages"] = missing_elsewhere
    return result
