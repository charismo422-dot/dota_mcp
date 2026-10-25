# `dota_mcp` — Dota 2 Workshop Tools MCP Server

> **[Русская версия документации (README.ru.md)](./README.ru.md)**
>
> **Project Status:** `Alpha` — tested on a single PC (Windows 11, Dota 2 7.41+) with Google Antigravity on one test mechanic (the [`mcp_test`](./examples/mcp_test/README.md) Ring of Fire ability). See [What Has Been Verified](#what-has-been-verified) below.
>
> **Disclaimer:** This is an unofficial, community project. It is not affiliated with, endorsed by, or sponsored by Valve Corporation. Dota 2 is a trademark of Valve Corporation.

`dota_mcp` is a specialized **Model Context Protocol (MCP)** server and agent workflow toolkit that enables AI coding agents to autonomously create, modify, compile, and live-debug **Dota 2 Custom Games** on Windows without hallucinating asset paths or Lua APIs.

---

## Key Capabilities (20 MCP Tools)

1. **Zero-Hallucination Asset & Sound Discovery (`pak01_dir.vpk`):**
   - `search_dota_assets`: Search models (`.vmdl`), particles (`.vpcf`), materials (`.vmat`), Panorama textures (`.vtex`), and scripts directly inside `pak01_dir.vpk`.
   - `search_sound_events`: Decompile `.vsndevts_c` files on the fly to extract exact sound event names (e.g., `Hero_Huskar.Inner_Fire.Cast`) and their source soundfiles for precaching.
   - `get_base_dota_definition`: Read official Dota 2 (7.41+) hero, ability, unit, and item KeyValues definitions (including nested `AbilityDefinitions` in split hero files).
2. **Deep Binary Asset Inspection (`Source2Viewer-CLI.exe`):**
   - `inspect_model`: Extract valid `ACT_DOTA_*` animation activities, attachment points (`attach_hitloc`, `attach_attack1`), and bone mappings from `.vmdl_c`.
   - `inspect_particle`: Extract used `Control Points` (`CP0`..`CPn`), child particles, initializers, and operators from `.vpcf_c`.
3. **Safe Map (`.vmap`) Editing & Compilation:**
   - `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, `remove_map_entity`, `compile_addon_resource`: Convert binary `.vmap` maps via `dmxconvert.exe`, add/remove point entities with valid UUIDs and `CVisibilityMgr` links without overflowing the LLM context window, and compile maps into `.vpk` (`.vmap_c`, `.gnv`) via `resourcecompiler.exe`.
4. **Addon Management, Localization & Auto-Precache:**
   - `create_or_configure_addon`, `get_addon_paths`, `upsert_localization` (`UTF-16`), `validate_and_sync_precache`: Validate Valve KeyValues syntax, catch misplaced files, compile custom `.png` icons to `.vtex_c`, and automatically generate `auto_precache.lua`.
5. **Live Engine Bridge (`NetCon` TCP port `2121`):**
   - `run_console_command`, `verify_vscript_api` (`script_help2`), `read_latest_console_log`: Launch custom games, hot-reload Lua scripts (`script_reload`), query live engine Lua API signatures, and inspect runtime stack traces.
   - `take_game_screenshot`: Save a `.jpg` of the running game (world + custom UI) so the agent can check visuals itself.
6. **Self-Diagnostics & Bug Logging:**
   - `run_mcp_self_test`, `log_bug_report`.

---

## What Has Been Verified

**Verified live** (Windows 11, Antigravity, `mcp_test` addon):
- `setup.py` install, `run_mcp_self_test`, `pak01_dir.vpk` indexing.
- `search_dota_assets`, `search_sound_events`, `get_base_dota_definition` (incl. 7.41+ nested `AbilityDefinitions`), `inspect_model`, `inspect_particle`.
- `create_or_configure_addon` (addon appears in the Workshop Tools UI), `prepare_map_from_template`, `add_map_entity`, `list_map_entities`, `compile_addon_resource` for `.vmap` (also covered by `tests/verify_phase0_acceptance.py`).
- `upsert_localization`, `validate_and_sync_precache` (KV validation + `auto_precache.lua` for Lua/KV assets).
- `run_console_command` (`dota_launch_custom_game`, `script_reload`), `verify_vscript_api`, `read_latest_console_log` over NetCon `2121`.
- Claude Code: staged live tests in the `mcp_lab` sandbox addon ([docs/TEST_PLAN.md](docs/TEST_PLAN.md), stages 0–10): ability, hero, waves and AI, item with own `.png` icon, Panorama HUD and world-space UI, map entities, own `.wav`/`.mp3` sounds, RU/EN localization, enemy heroes under Lua AI, cutscene with own full-screen images and `take_game_screenshot`.

**Not verified yet:**
- Compiling materials via `compile_addon_resource`.
- `remove_map_entity` on brush/mesh entities.
- Windows 10, other PCs, non-default Steam library layouts.
- Cursor, Windsurf, Codex and other agents.
- Multiplayer and Workshop publishing.

---

## System Requirements

- **OS:** Windows 10 / 11 (64-bit) — *required by Valve's `dmxconvert.exe` and `resourcecompiler.exe`*.
- **Dota 2 + Workshop Tools DLC:** Installed via Steam (in Steam Library -> right-click **Dota 2** -> **Properties** -> **DLC** -> check **Dota 2 Workshop Tools DLC**).
- **Python:** Python `3.10` or newer (`python` and `pip` in `PATH`).
- **Git:** Installed and available in `PATH`.

---

## Quick Start

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/charismo422-dot/dota_mcp.git
   cd dota_mcp
   ```

2. **Run the idempotent installer:**
   ```powershell
   python setup.py
   ```
   *(Or run `.\setup.ps1` in PowerShell. If Dota 2 is installed in a non-standard directory, pass `python setup.py --dota-path "D:\Path\To\dota 2 beta"`).*

   **What `setup.py` does automatically:**
   - Creates `.venv` and installs Python dependencies (`mcp>=2.3.0,<3.0.0`, `vpk`, `vdf`, `requests`).
   - Locates your Dota 2 installation and verifies Workshop Tools binaries (`dmxconvert.exe`, `resourcecompiler.exe`, `addon_template`).
   - Downloads the latest `Source2Viewer-CLI.exe` into `bin/` (**~110 MB**; ~120 MB on disk with its DLLs).
   - If Antigravity is installed (`~/.gemini` exists) or `--antigravity` is passed, safely merges `dota2-workshop-mcp` into `~/.gemini/config/mcp_config.json` (preserving your existing MCP servers). Otherwise `~/.gemini` is not created.
   - Generates `.mcp.json` + `.claude/skills/` for Claude Code.
   - Runs `run_mcp_self_test` to confirm readiness.
   - Prints a ready-to-paste MCP config snippet (`command`, `args`, `cwd`, `env` with `PYTHONPATH`) for manually connecting other agents.

3. **Restart or refresh your AI agent** so it loads the `dota2-workshop-mcp` server and project rules.

---

## Mandatory Dota 2 Launch Settings & Windows Permissions

1. **Steam Launch Options for Dota 2:**
   In Steam (**Dota 2 -> Properties -> General -> Launch Options**), set:
   ```text
   -netconport 2121 -console -condebug
   ```
   > **Note:** Do **not** add `-tools` to Steam Launch Options. Instead, select **Launch Dota 2 - Tools** from the standard Steam launch dialog when starting the game. Port `2121` is used instead of `29000` to avoid colliding with `vconsole2.exe`'s binary protocol.

2. **Do NOT Run Dota 2 or Your Agent as Administrator (`RUNASADMIN`):**
   - Neither `dota2.exe`, `dota2cfg.exe`, nor your AI agent IDE (e.g. **Antigravity**) should have *"Run this program as an administrator"* checked in Windows Compatibility Properties, and neither should be launched from an elevated terminal.
   - If `dota2.exe` has the `RUNASADMIN` flag set, the non-elevated Workshop Tools launcher (`dota2cfg.exe`) will fail with `Failed to launch` (`WinError 740: ERROR_ELEVATION_REQUIRED`).

---

## Supported AI Agents

| Agent | Support Status | How Rules & MCP Are Loaded |
| :--- | :--- | :--- |
| **Google Antigravity** | **Verified** (one PC, one test mechanic) | Reads `GEMINI.md` -> `@[AGENTS.md](./AGENTS.md)`, skill in `.agents/skills/dota2-custom-game-dev/`, and MCP config in `~/.gemini/config/mcp_config.json`. |
| **Claude Code** | **Verified: connection & self-test** | Reads `CLAUDE.md` -> `@AGENTS.md`, skill copied to `.claude/skills/dota2-custom-game-dev/`, and MCP config generated in `.mcp.json`. |
| **Other Agents (Cursor, Windsurf, Codex)** | **Unverified** | Rules in `AGENTS.md`; paste the MCP config snippet printed at the end of `python setup.py` into your agent's MCP settings. |

---

## Working Example (`examples/mcp_test`)

See [`examples/mcp_test/`](./examples/mcp_test/README.md) for a complete, verified custom game example featuring the **Ring of Fire (`mcp_ring_of_fire`)** Lua ability, automatic precache, Russian/English localization, passive target spawning, and auto-respawn logic.

To run the automated acceptance test suite for `.vmap` editing and compilation at any time:
```powershell
.\.venv\Scripts\python.exe tests\verify_phase0_acceptance.py
```

---

## Known Limitations (Alpha)

- **Point Entities in `.vmap`:** `remove_map_entity` is designed for point entities (`CMapEntity` without nested brush/mesh children). Removing complex brush entities does not recursively strip nested mesh element UUIDs.
- **NetCon Single-Command Buffer:** Dota 2's TCP NetCon socket truncates single-command bursts larger than ~3,600 lines; `verify_vscript_api` automatically falls back to reading the full `script_help2` dump from `game/dota/console.log` (requires `-condebug`).
- **Windows Only:** Map conversion and asset compilation rely on Valve's win64 Workshop Tools binaries (`dmxconvert.exe`, `resourcecompiler.exe`).

---

## Documentation

- [Agent Rules & Invariants (`AGENTS.md`)](./AGENTS.md)
- [Technical Specification (`docs/TECHNICAL_SPEC.md`)](./docs/TECHNICAL_SPEC.md)
- [Self-Check Protocol (`docs/SELF_CHECK_PROTOCOL.md`)](./docs/SELF_CHECK_PROTOCOL.md)
- [Bug & Fix Log (`docs/BUG_LOG.md`)](./docs/BUG_LOG.md)
- [Reference Format Samples (`docs/reference_samples/`)](./docs/reference_samples/)

---

## License

No license has been chosen yet. Until one is added, all rights are reserved by the author.

## Disclaimer

`dota_mcp` is an unofficial project and is not affiliated with or endorsed by Valve Corporation. Dota 2, Steam, and Source 2 are trademarks of Valve Corporation.
