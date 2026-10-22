# Staged Live Test Plan (`TEST_PLAN.md`)

Short live checks of `dota2-workshop-mcp` against real custom-game tasks. All stages use one sandbox addon (`mcp_lab`), each stage fits one short session. Record results in [LESSONS.md](./LESSONS.md); bugs via `log_bug_report`.

Prerequisite for every stage: Dota 2 launched via **Launch Dota 2 - Tools** with `-netconport 2121 -console -condebug`.

Every stage also checks the error channel: after each change, `script_reload` (or relaunch) and `read_latest_console_log` must show zero Lua errors; if errors appear, they must be readable with file and line.

| # | Stage | What is verified | Status |
|---|---|---|---|
| 0 | Setup | `create_or_configure_addon`, `prepare_map_from_template`, `compile_addon_resource` (map), `dota_launch_custom_game` | done (2026-10-22) |
| 1 | Ability | Lua ability + modifier + particle + sound: `search_dota_assets`, `inspect_particle` (CPs), `search_sound_events`, `verify_vscript_api`, `validate_and_sync_precache`, hot reload via `script_reload` | done (2026-10-22): autotest PASS, hot reload PASS; sound precache gap found |
| 2 | Hero | Custom hero based on a stock one: `get_base_dota_definition`, `inspect_model` (activities/attachments), 4 abilities, hero pick | done (2026-10-22): autotest PASS (stats, slots, projectile+stun, aura, ultimate thinker) |
| 3 | Creeps & AI | Timed creep waves, spawn points via `add_map_entity`, simple AI | done (2026-10-22): autotest PASS (spawners, AI attached, chase, telegraphed elite slam, wave timer) |
| 4 | Item | Custom item with custom `.png` icon compiled to `.vtex_c` (unverified area) | done (2026-10-22): autotest PASS (stats, rift pull motion controller, silence, damage); icon compile fixed |
| 5 | Panorama | Simple HUD panel (score/timer), Lua → JS events, `compile_addon_resource` for `.xml`/`.css`/`.js` (unverified area) | done (2026-10-22): autotest PASS (Lua→JS→Lua round trip, kill counter/energy); compile of manifest + layout + css + js verified |
| 5b | World-space UI | Floating damage numbers, charges above the hero's HP bar, NPC dialog with choices (typewriter, glass style) | done (2026-10-22): autotest PASS |
| 6 | Map | Trees, shop, spawns: `add_map_entity`, `list_map_entities`, `remove_map_entity`, recompile | todo |
| 7 | Sound | Stock sound events; check whether custom sound files can be added (expected gap) | todo |
| 8 | Localization | RU/EN strings via `upsert_localization` visible in game | todo |

Stage 8 of the earlier draft ("break Lua on purpose, then fix") was dropped as a separate stage: the same agent breaking and fixing proves nothing. Instead the error channel (log capture + hot reload) is checked inside every stage.
