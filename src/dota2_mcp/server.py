"""Main FastMCP Server entry point exposing all 15 Dota 2 Workshop Tools functions."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from . import (
    addon_manager,
    asset_inspector,
    diagnostics,
    netcon_bridge,
    vmap_builder,
    vpk_explorer,
)

mcp = FastMCP("dota2-workshop-mcp")


# ---------------------------------------------------------------------------
# Module 1: VPK Asset & Script Explorer
# ---------------------------------------------------------------------------


@mcp.tool()
def search_dota_assets(
    query: str, asset_type: str = "all", limit: int = 25
) -> dict[str, Any]:
    """Search Dota 2 pak01_dir.vpk for real asset paths (.vmdl, .vpcf, .vsndevts, .vmat, .png).
    Automatically strips the compiled '_c' suffix so paths are ready for Lua, KV, and .vmap.
    Valid asset_type values: 'model', 'particle', 'sound', 'material', 'panorama', 'script', 'all'.
    """
    return vpk_explorer.search_dota_assets(query=query, asset_type=asset_type, limit=limit)


@mcp.tool()
def get_base_dota_definition(category: str, name: str) -> dict[str, Any]:
    """Extract standard Dota 2 KeyValues block from pak01_dir.vpk (npc_heroes.txt, npc_abilities.txt, npc_units.txt, items.txt).
    Valid category values: 'hero', 'ability', 'unit', 'item'.
    """
    return vpk_explorer.get_base_dota_definition(category=category, name=name)


# ---------------------------------------------------------------------------
# Module 2: Deep Model & Particle Inspector
# ---------------------------------------------------------------------------


@mcp.tool()
def inspect_model(model_path: str) -> dict[str, Any]:
    """Inspect a Dota 2 model (.vmdl) to extract valid ACT_DOTA_* animation activities and attach_* points."""
    return asset_inspector.inspect_model(model_path=model_path)


@mcp.tool()
def inspect_particle(particle_path: str) -> dict[str, Any]:
    """Inspect a Dota 2 particle (.vpcf) to extract active Control Points (CP0..CPn), child particles, and operators."""
    return asset_inspector.inspect_particle(particle_path=particle_path)


# ---------------------------------------------------------------------------
# Module 3: Addon Manager, KV Validator, Precache & Localization
# ---------------------------------------------------------------------------


@mcp.tool()
def create_or_configure_addon(
    addon_name: str,
    maps: list[str],
    max_players: int = 10,
    team_count: int = 2,
) -> dict[str, Any]:
    """Create a new Dota 2 custom game addon from addon_template (if needed) and configure addoninfo.txt."""
    return addon_manager.create_or_configure_addon(
        addon_name=addon_name,
        maps=maps,
        max_players=max_players,
        team_count=team_count,
    )


@mcp.tool()
def get_addon_paths(addon_name: str) -> dict[str, Any]:
    """Return exact canonical directories for game/ (runtime Lua, KV, localization) vs content/ (source .vmap, .xml/.css/.js Panorama, .png spellicons/items requiring resourcecompiler.exe)."""
    return addon_manager.get_addon_paths(addon_name=addon_name)


@mcp.tool()
def validate_and_sync_precache(addon_name: str) -> dict[str, Any]:
    """Validate syntax of all Valve KeyValues (.txt/.kv) files, detect misplaced files between game/ and content/ (including obsolete flash3 paths), auto-compile custom .png icons to .vtex_c, verify every referenced .vmdl/.vpcf/.vsndevts exists in VPK, and auto-generate Precache in addon_game_mode.lua."""
    return addon_manager.validate_and_sync_precache(addon_name=addon_name)


@mcp.tool()
def upsert_localization(
    addon_name: str, language: str, tokens: dict[str, str]
) -> dict[str, Any]:
    """Add or update localization strings in game/dota_addons/<addon_name>/resource/addon_<language>.txt."""
    return addon_manager.upsert_localization(
        addon_name=addon_name, language=language, tokens=tokens
    )


# ---------------------------------------------------------------------------
# Module 4: .vmap Map Builder & Resource Compiler
# ---------------------------------------------------------------------------


@mcp.tool()
def prepare_map_from_template(
    addon_name: str, map_name: str, source_template: str = "template_map"
) -> dict[str, Any]:
    """Copy a template .vmap into content/dota_addons/<addon_name>/maps/<map_name>.vmap and convert it via dmxconvert.exe to editable keyvalues2 text."""
    return vmap_builder.prepare_map_from_template(
        addon_name=addon_name, map_name=map_name, source_template=source_template
    )


@mcp.tool()
def list_map_entities(
    addon_name: str, map_name: str, classname_filter: str = ""
) -> dict[str, Any]:
    """Return a compact list of all CMapEntity nodes in a .vmap (id, classname, targetname, origin, angles, properties) without loading heavy mesh data."""
    return vmap_builder.list_map_entities(
        addon_name=addon_name, map_name=map_name, classname_filter=classname_filter
    )


@mcp.tool()
def add_map_entity(
    addon_name: str,
    map_name: str,
    classname: str,
    origin: str,
    targetname: str = "",
    angles: str = "0 0 0",
    scales: str = "1 1 1",
    properties: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Add a new entity (e.g. info_player_start_goodguys, npc_dota_spawner, ent_dota_tree, prop_dynamic, info_target) to the .vmap at coordinates 'X Y Z'."""
    return vmap_builder.add_map_entity(
        addon_name=addon_name,
        map_name=map_name,
        classname=classname,
        origin=origin,
        targetname=targetname,
        angles=angles,
        scales=scales,
        properties=properties,
    )


@mcp.tool()
def remove_map_entity(
    addon_name: str, map_name: str, targetname_or_id: str
) -> dict[str, Any]:
    """Remove an entity from the .vmap by its targetname or element UUID."""
    return vmap_builder.remove_map_entity(
        addon_name=addon_name, map_name=map_name, targetname_or_id=targetname_or_id
    )


@mcp.tool()
def compile_addon_resource(addon_name: str, resource_rel_path: str) -> dict[str, Any]:
    """Compile a map ('maps/my_map.vmap'), Panorama file, or material via resourcecompiler.exe and return build status and error logs."""
    return vmap_builder.compile_addon_resource(
        addon_name=addon_name, resource_rel_path=resource_rel_path
    )


# ---------------------------------------------------------------------------
# Module 5: Live Engine & Console Bridge (NetCon)
# ---------------------------------------------------------------------------


@mcp.tool()
def run_console_command(command: str, wait_response_ms: int = 1200) -> dict[str, Any]:
    """Send a console command to running Dota 2 via NetCon TCP port 29000 (e.g. 'dota_launch_custom_game <addon> <map>', 'script_reload') and read console logs/errors."""
    return netcon_bridge.run_console_command(
        command=command, wait_response_ms=wait_response_ms
    )


@mcp.tool()
def verify_vscript_api(search_term: str) -> dict[str, Any]:
    """Query the live Dota 2 engine (7.41+) via 'script_help2 <search_term>' to verify real Lua functions, classes, and modifier constants directly from the game binary."""
    return netcon_bridge.verify_vscript_api(search_term=search_term)


@mcp.tool()
def read_latest_console_log(tail_lines: int = 80) -> dict[str, Any]:
    """Read the latest lines and Lua errors from game/dota/console.log on disk (when Dota 2 is launched with -condebug)."""
    return netcon_bridge.read_latest_console_log(tail_lines=tail_lines)


# ---------------------------------------------------------------------------
# Module 6: Diagnostics & Bug Logging
# ---------------------------------------------------------------------------


@mcp.tool()
def run_mcp_self_test() -> dict[str, Any]:
    """Verify Dota 2 installation paths, pak01_dir.vpk access, dmxconvert.exe, resourcecompiler.exe, Decompiler CLI, and NetCon port status."""
    return diagnostics.run_mcp_self_test(auto_download_decompiler=True)


@mcp.tool()
def log_bug_report(
    component: str,
    symptom: str,
    root_cause: str,
    fix_applied: str,
    prevention_rule: str,
) -> dict[str, Any]:
    """Record a discovered bug, root cause, fix, and prevention rule into docs/BUG_LOG.md."""
    return diagnostics.log_bug_report(
        component=component,
        symptom=symptom,
        root_cause=root_cause,
        fix_applied=fix_applied,
        prevention_rule=prevention_rule,
    )


if __name__ == "__main__":
    mcp.run()
