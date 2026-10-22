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
For complete architecture details, tool signatures, mandatory Windows pre-launch fixes, self-check questions, 7.41+ paths/icons/Lua reference, and bug logs, consult:
- **MANDATORY FIRST READ ON WINDOWS:** [CODE_REVIEW_TODO.md](../../../docs/CODE_REVIEW_TODO.md)
- [TECHNICAL_SPEC.md](../../../docs/TECHNICAL_SPEC.md)
- [SELF_CHECK_PROTOCOL.md](../../../docs/SELF_CHECK_PROTOCOL.md)
- [DOTA2_741_REFERENCE.md](./references/DOTA2_741_REFERENCE.md)
- [BUG_LOG.md](../../../docs/BUG_LOG.md)

## Windows Environment Bootstrap & Mandatory Phase 0 Fix (When asked to set up on Windows PC)
If the user opens this repository on their Windows PC and asks to set up or continue the project:
1. **Read [CODE_REVIEW_TODO.md](../../../docs/CODE_REVIEW_TODO.md) immediately.** Do NOT start building a custom game before completing Phase 0 (Steps 1–4 in `CODE_REVIEW_TODO.md`).
2. Create a Python virtual environment and install dependencies:
   `python -m venv .venv`
   `.venv\Scripts\pip install -r requirements.txt`
3. Run the bootstrap diagnostic to verify Dota 2 paths and automatically download `Source2Viewer-CLI.exe` / `Decompiler.exe`:
   `.venv\Scripts\python -m src.dota2_mcp.diagnostics --bootstrap`
4. Convert the real `template_map.vmap` via `dmxconvert.exe` to inspect actual `CMapEntity` KeyValues2 structure, fix 🔴 1–4 and 🟠 5–11 in `src/dota2_mcp/`, and verify map compilation with `resourcecompiler.exe`.
5. Register `dota2-workshop-mcp` inside `%USERPROFILE%\.gemini\config\mcp_config.json` and run `run_mcp_self_test`.

## Mandatory Rules for Dota 2 Asset & Code Generation

1. **Zero Hallucinated Assets:**
   - NEVER guess or invent `.vmdl`, `.vpcf`, `.vsndevts`, or `.vmat` paths.
   - ALWAYS call `search_dota_assets` first to verify exact paths inside `pak01_dir.vpk`.
   - When creating custom units or abilities with animations/particles, call `inspect_model` to get valid `ACT_DOTA_*` activities and `attach_*` points, and `inspect_particle` to verify `Control Points` (`CP0`..`CPn`).

2. **Safe `.vmap` Editing:**
   - NEVER read raw `.vmap` files directly into context (they can exceed hundreds of megabytes of mesh data).
   - ALWAYS use `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, and `remove_map_entity`.
   - After modifying `.vmap` or Panorama files, ALWAYS run `compile_addon_resource`.

3. **KV Validation & Precache Sync:**
   - Before launching or reloading a custom game, ALWAYS run `validate_and_sync_precache` to verify Valve KeyValues syntax and register all models/particles/sounds in `Precache`.
   - Always add human-readable names and descriptions via `upsert_localization`.

4. **Live Testing via NetCon:**
   - Use `run_console_command` to launch the map (`dota_launch_custom_game <addon> <map>`) or hot-reload scripts (`script_reload`) and inspect Lua runtime logs.
