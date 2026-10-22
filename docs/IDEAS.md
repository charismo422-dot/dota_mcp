# Idea Bank: MCP Server Features (`IDEAS.md`)

Ideas for new `dota2-workshop-mcp` tools and improvements. Custom-game ideas are kept privately by the owner, not here.

**Agents:** append an idea when the owner proposes one or when a task reveals a missing capability. Update the status as work progresses.

Format: **Name** — what it does / why — status (`idea` / `discussing` / `in progress` / `done` / `rejected`).

## New features (ordered by value for custom-game development)

1. **Scaffold from description** — one call creates ability/item/hero/modifier KV + Lua + localization + precache from a short spec — `idea`
2. **Cross-reference validator** — before launch, detect broken links: abilities referenced by heroes/units that don't exist, missing `ScriptFile` Lua files, unknown modifiers, missing localization keys — `idea`
3. **Offline VScript API cache** — dump `script_help2` once, then verify Lua calls without a running game — `done` (2026-10-22, in `verify_vscript_api`)
4. **Automated mechanic tests** — Lua harness spawns hero/targets, casts the ability, asserts damage/effects via console log — `idea`
5. **In-game screenshots** — capture a screenshot so the agent can visually check particles and UI (console command to be verified) — `idea`
6. **Custom sounds & music** — add own audio files, generate `.vsndevts`, compile — `idea`
7. **Particle recolor/resize** — copy a stock `.vpcf` and change color/size without the particle editor — `idea`
8. **Multiplayer test with bots / fake clients** — launch with extra players to test team logic (commands to be verified) — `idea`
9. **Custom model import** — compile own 3D models (e.g. FBX) into `.vmdl` (voxel/"Minecraft-like" blocks) — `idea`
10. **Map generation from templates** — arena, corridors, maze from a description; complex, last priority — `idea`

## Improvements to existing tools

- **Resolve sound events in precache** — `validate_and_sync_precache` maps sound event names used in Lua/KV to their `.vsndevts` (cached event index built once from the VPK) and precaches them; currently sounds silently go un-precached. High priority — `idea`
- **`verify_vscript_api` from a cached dump** — run `script_help2` once per game build, then answer from the cache; avoids flooding `console.log` and duplicate matches — `done` (also covers feature #3)
- **Filter `compile_addon_resource` noise** — collapse repeated `generic.vfx` shader errors and known missing base files; keep only real failures — `idea`
- **`verify_vscript_api` live fallback for constants** — when the cache has no match, ask the running game for `type(<name>)`/value (constants like `FIND_CLOSEST` are not in the dump) — `idea`
- **`add_item_to_shop` tool** — create the addon `shops.txt` from the stock VPK copy (first time) and insert custom items into a chosen category — `idea`
- **Looping-sound lint** — warn when Lua emits a known looping sound event with `EmitSoundOnLocationWithCaster` (cannot be stopped) — `idea`
- **`create_minimap` tool** — one call: add/update `dota_minimap_boundary` pair, disconnect, compile map, relaunch, clear units, run `dota_minimap_create`, verify `resource/overviews/<map>.txt` — `idea`
- **Compact `get_base_dota_definition`** — optional `fields` filter / summary mode (abilities, stats only) instead of the full ≈ 10 KB hero block with bot builds and item slots — `idea`
- **Precache units created from Lua** — detect `CreateUnitByName("x", ...)` literals and add `PrecacheUnitByNameSync` to `auto_precache.lua`; otherwise spawned units are invisible — `idea`
- **Compact `list_map_entities`** — default to id/classname/targetname/origin only, full properties on request; saves context — `idea`

- **Filter console noise** — split `errors_and_warnings` into addon errors (Lua, own assets) vs known base-game noise; trim server-info dumps from `read_latest_console_log` — `done` (noise filter, `grep`, `only_errors`)

## Verification gaps

- **Verify `.png` icon compilation live** — see [TEST_PLAN.md](./TEST_PLAN.md) stage 4 — `idea`
- **Verify Panorama compilation live** — see [TEST_PLAN.md](./TEST_PLAN.md) stage 5 — `idea`
