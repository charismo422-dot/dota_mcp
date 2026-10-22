---
name: dota2-custom-game-dev
description: >-
  Standard workflow and MCP tool usage guide for creating, modifying, compiling,
  and debugging Dota 2 Custom Games using Workshop Tools and the dota_mcp server.
  Activate whenever the user asks to create or edit a Dota 2 custom game, map,
  ability, unit, UI, or the dota_mcp server itself.
---

# Dota 2 Custom Game Development & MCP Workflow

This skill enforces the mandatory architecture and step-by-step workflow for building Dota 2 custom games via the `dota_mcp` MCP server.

## Full Technical Specification & Self-Check Protocol
For complete architecture details, tool signatures, self-check questions, 7.41+ paths/icons/Lua reference, and bug logs, consult:
- [AGENTS.md](../../../AGENTS.md)
- [TECHNICAL_SPEC.md](../../../docs/TECHNICAL_SPEC.md)
- [SELF_CHECK_PROTOCOL.md](../../../docs/SELF_CHECK_PROTOCOL.md)
- [DOTA2_741_REFERENCE.md](./references/DOTA2_741_REFERENCE.md)
- [BUG_LOG.md](../../../docs/BUG_LOG.md)

## First-Time Windows Setup
If the environment is not yet initialized on a Windows PC:
1. Run the idempotent setup script from the repository root:
   ```powershell
   python setup.py
   ```
   *(or `.\setup.ps1`).* This creates `.venv`, installs dependencies, downloads `Source2Viewer-CLI.exe`, locates Dota 2 + Workshop Tools, registers the MCP server for Antigravity and Claude Code, and copies this skill to `.claude/skills/`.
2. Call `run_mcp_self_test` to verify that `pak01_dir.vpk`, `dmxconvert.exe`, `resourcecompiler.exe`, and `Source2Viewer-CLI.exe` are ready.

## Mandatory Rules for Dota 2 Asset & Code Generation

1. **Zero Hallucinated Assets & APIs:**
   - NEVER guess or invent `.vmdl`, `.vpcf`, `.vsndevts`, `.vmat`, or `.vtex` paths.
   - ALWAYS call `search_dota_assets` and `search_sound_events` first to verify exact paths and sound event names inside `pak01_dir.vpk`.
   - Call `get_base_dota_definition` to inspect real Dota 2 (7.41+) hero, ability, unit, or item KeyValues definitions.
   - When creating custom units or abilities with animations/particles, call `inspect_model` to get valid `ACT_DOTA_*` activities and `attach_*` points, and `inspect_particle` to verify `Control Points` (`CP0`..`CPn`).
   - Verify Lua VScript API functions and constants via `verify_vscript_api` against the running Dota 2 engine.

2. **Safe `.vmap` Editing:**
   - NEVER read raw `.vmap` files directly into context (they can exceed megabytes of mesh data).
   - ALWAYS use `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, and `remove_map_entity`.
   - After modifying `.vmap` or Panorama files, ALWAYS run `compile_addon_resource`.

3. **KV Validation & Precache Sync:**
   - Before launching or reloading a custom game, ALWAYS run `validate_and_sync_precache` to verify Valve KeyValues syntax and register all models/particles/sounds in `auto_precache.lua`.
   - Always add human-readable names and descriptions via `upsert_localization`.

4. **Live Testing via NetCon:**
   - Use `run_console_command` to launch the map (`dota_launch_custom_game <addon> <map>`) or hot-reload scripts (`script_reload`) and check `read_latest_console_log` to ensure zero Lua errors.
