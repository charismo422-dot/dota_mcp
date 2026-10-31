# Idea Bank: MCP Server Features (`IDEAS.md`)

Ideas for new `dota2-workshop-mcp` tools and improvements. Custom-game ideas are kept privately by the owner, not here.

**Agents:** append an idea when the owner proposes one or when a task reveals a missing capability. Update the status as work progresses.

Format: **Name** — what it does / why — status (`idea` / `discussing` / `in progress` / `done` / `rejected`).

## New features (ordered by value for custom-game development)

1. **Scaffold from description** — one call creates ability/item/hero/modifier KV + Lua + localization + precache from a short spec — `done` (2026-10-25, `scaffold_game_element`: ability/item/modifier; hero not covered)
2. **Cross-reference validator** — before launch, detect broken links: abilities referenced by heroes/units that don't exist, missing `ScriptFile` Lua files, unknown modifiers, missing localization keys — `partly done` (localization part in `validate_and_sync_precache`, stage 8)
3. **Offline VScript API cache** — dump `script_help2` once, then verify Lua calls without a running game — `done` (2026-10-22, in `verify_vscript_api`)
4. **Automated mechanic tests** — Lua harness spawns hero/targets, casts the ability, asserts damage/effects via console log — `idea`
5. **In-game screenshots** — capture a screenshot so the agent can visually check particles and UI (console command to be verified) — `idea`
6. **Custom sounds & music** — add own audio files, generate `.vsndevts`, compile — `partly done` (manual pipeline verified in stage 7; a one-call `add_custom_sound` tool — wav → `sounds/`, upsert event in `.vsndevts`, compile — is the next step)
7. **Particle recolor/resize** — copy a stock `.vpcf` and change color/size without the particle editor — `idea`
8. **Multiplayer test with bots / fake clients** — launch with extra players to test team logic (commands to be verified) — `idea`
9. **Custom model import** — compile own 3D models (e.g. FBX) into `.vmdl` (voxel/"Minecraft-like" blocks) — `idea`
10. **Map generation from templates** — arena, corridors, maze from a description; complex, last priority — `idea`

## Improvements to existing tools

- **Resolve sound events in precache** — `validate_and_sync_precache` maps sound event names used in Lua/KV to their `.vsndevts` (cached event index built once from the VPK) and precaches them; currently sounds silently go un-precached. High priority — `done` (stage 7; also flags unknown names)
- **`verify_vscript_api` from a cached dump** — run `script_help2` once per game build, then answer from the cache; avoids flooding `console.log` and duplicate matches — `done` (also covers feature #3)
- **Filter `compile_addon_resource` noise** — collapse repeated `generic.vfx` shader errors and known missing base files; keep only real failures — `idea`
- **`verify_vscript_api` live fallback for constants** — when the cache has no match, ask the running game for `type(<name>)`/value (constants like `FIND_CLOSEST` are not in the dump) — `idea`
- **`verify_panorama_api` tool** — cache `cl_panorama_script_help_2` per build (like the Lua cache) and search JS bindings; optionally CSS properties via `dump_panorama_css_properties` — `idea` (high value for UI work)
- **Panorama compile guard** — `compile_addon_resource` warns about includes of stock files without SDK source (`dotastyles.css`) and about compiling a manifest whose referenced layouts don't exist yet — `idea`
- **Listener-stacking lint** — warn when Lua calls `ListenToGameEvent` at file load without `StopListeningToGameEvent` of a stored id — `idea`
- **Batch map edits** — `add_map_entities` (list) / pattern helpers (ring, grid, line) in one call — `idea` (high value for map work)
- **Brush triggers in `.vmap`** — create box-shaped `trigger_*` meshes (shop, no-wards, custom triggers) so maps don't need Lua workarounds — `idea`
- **FGD lookup tool** — search `dota.fgd`/`base.fgd` for an entity class and its keys/choices before placing it — `idea`
- **`add_item_to_shop` tool** — create the addon `shops.txt` from the stock VPK copy (first time) and insert custom items into a chosen category — `idea`
- **Looping-sound lint** — warn when Lua emits a known looping sound event with `EmitSoundOnLocationWithCaster` (cannot be stopped) — `idea`
- **`create_minimap` tool** — one call: add/update `dota_minimap_boundary` pair, disconnect, compile map, relaunch, clear units, run `dota_minimap_create`, verify `resource/overviews/<map>.txt` — `idea`
- **Compact `get_base_dota_definition`** — optional `fields` filter / summary mode (abilities, stats only) instead of the full ≈ 10 KB hero block with bot builds and item slots — `idea`
- **Precache units created from Lua** — detect `CreateUnitByName("x", ...)` literals and add `PrecacheUnitByNameSync` to `auto_precache.lua`; otherwise spawned units are invisible — `idea`
- **Scope console errors to the latest launch** — `read_latest_console_log` / `run_console_command` should report only errors after the last `dota_launch_custom_game` / VM init; old errors look current and waste context — `idea`
- **Enemy hero helper** — template/tool that spawns a stock hero for the enemy team with level, items and leveled abilities (names validated via the hero KV) plus an order-based AI skeleton (attack, cast, retreat) — `idea`
- **AI profiles for any stock hero** — the stage 9 hunter AI has hand-written profiles only for Sven, Lina, Axe; for a real project generate a per-hero profile (which spells to combo, range/kite, escape and self-help items) from the hero's ability KV (`AbilityBehavior`, cast range, damage/stun values) and let the agent tune it per hero — `idea` (owner request, 2026-10-25)
- **Precache stock heroes created from Lua** — detect `CreateUnitByName("npc_dota_hero_*")` literals (extension of the unit precache idea) — `idea`
- **Compact `list_map_entities`** — default to id/classname/targetname/origin only, full properties on request; saves context — `idea`
- **Cutscene template** — reusable Lua timeline + Panorama overlay from stage 10 (camera thinker path, HUD hide/restore, slides with zoom/shake, subtitles, hold-to-skip, sound length from `GetSoundDuration`); the agent fills shots/images/texts — `idea`
- **`take_game_screenshot` options** — downscale (`screenshot_width`/`screenshot_height`) or crop a region to save image tokens; wait N seconds before the shot; a burst of shots for animations — `idea`
- **Panorama edit guard** — after a `.xml`/`.js` change in a running game warn that hot reload keeps the old JS context (stale probes, frozen animation) and suggest relaunching the map before tests — `idea`
- **Bring Dota to the foreground for screenshots** — `take_game_screenshot` option that focuses the Dota window first (and back afterwards): an unfocused window is not redrawn, the shot repeats a stale frame — `idea` (stage 11)
- **Game-flow template** — reusable lobby (host-only settings via net table, countdown, start button) + lives counter + EndScreen with stats from stage 11; the agent fills settings and stats — `idea`

- **Filter console noise** — split `errors_and_warnings` into addon errors (Lua, own assets) vs known base-game noise; trim server-info dumps from `read_latest_console_log` — `done` (noise filter, `grep`, `only_errors`)

- **Language voice packs in sound search** — `search_sound_events`/`search_dota_assets` see only `game/dota/pak01`; add `game/dota_<language>/pak01` (e.g. `dota_russian`: only `sounds/vo/<hero>/` files, same event names) and report which heroes have the language's voice.
- **Stock compiled maps in asset search** — `game/dota/maps/*.vpk` (dota_683, dota_685, …) are invisible to `search_dota_assets`; list them with their inner `maps/<name>.vmap_c` name.

- **Scaffold: more effects** — `scaffold_game_element`: projectile (tracking/linear), DoT, silence/root/disarm, auras, charges, hero kind; set known particle CPs (radius) from `inspect_particle` — `idea`
- **Scaffold: autotest stub** — generate a console-command autotest for each scaffolded element (spawn target, cast, assert effects) — `idea`

## Verification gaps

- **Verify `.png` icon compilation live** — see [TEST_PLAN.md](./TEST_PLAN.md) stage 4 — `done` (stage 4 icon, stage 10 full-screen 1920×1080 slides)
- **Verify Panorama compilation live** — see [TEST_PLAN.md](./TEST_PLAN.md) stage 5 — `done` (stages 5, 5b, 10)
- MCP: `validate_and_sync_precache` could warn about `CustomGameEventManager:RegisterListener` at module top level (listener lost before Activate).
- mcp_lab: draw the zone border on the ground (particle ring / line along the polygon) — owner can not see the zone (stage 12).
- mode-1: remove a stock map unit that spawns after the start scan (periodic check) and fix its zone to one place.
- MCP: `get_base_dota_definition` — a compact mode (only `AbilityN` names + behavior/cast range) to save context.
- mode-1: per-hero AI tuning for every hunter profile; hunter power shown in the HUD.
- mode-1: draw the zone border in the world (owner could not see it); idea only.
- mode-1: draw the inner zone (pit) outline in the world too, not only the outer border.
- mode-1: show the "no attacks" state on hunters (icon/text) so the player sees why they only cast.
- mode-1: stock warning "unknown modifier type modifier_life_stealer_open_wounds_intrinsic" when Lifestealer hunter spawns — harmless, not fixed.
