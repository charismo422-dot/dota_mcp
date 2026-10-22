# Lessons Learned (`LESSONS.md`)

Agent self-learning log: what works, what does not, and how it was solved. Broader than [BUG_LOG.md](./BUG_LOG.md) (which records MCP/addon bugs via `log_bug_report`): also covers workflow, tooling, environment and agent-behaviour findings.

**Agents:** read this file before starting a task; append an entry after finishing one whenever something new was learned. Keep entries short. If an entry turns out wrong, fix or delete it.

Entry format:

```
### YYYY-MM-DD — <short topic>
- **Works / Doesn't work:** ...
- **Solution / Rule:** ...
```

---

### 2026-10-22 — Antigravity global rules loading
- **Doesn't work:** `~/.gemini/config/rules/*.md` without YAML frontmatter (`trigger: always_on|model_decision|glob|manual`) is silently ignored. `~/.gemini/GEMINI.md` and `~/.gemini/config/GEMINI.md` both load and stack, so duplicates double the rules.
- **Solution / Rule:** keep one standalone global rules file; modular rule files always need frontmatter (source: antigravity.google/docs/rules).

### 2026-10-22 — Antigravity MCP config path
- **Works:** the documented global MCP config is `~/.gemini/config/mcp_config.json` (source: antigravity.google/docs/mcp). `~/.gemini/antigravity/mcp_config.json` is not documented.
- **Solution / Rule:** `setup.py` writes only the documented path and only when `~/.gemini` exists or `--antigravity` is passed.

### 2026-10-22 — Testing setup.py safely
- **Rule:** always run `python setup.py --home <temp dir>` when testing, so real user configs are untouched. Note: `.mcp.json` and `.claude/skills/` in the repo are still rewritten (gitignored).

### 2026-10-22 — Test plan stage 0 (offline part, `mcp_lab`)
- **Works:** `create_or_configure_addon`, `prepare_map_from_template`, `compile_addon_resource` for `.vmap` (12 compiled, 0 failed, ~9 s) without a running game. `Error creating shader generic.vfx` and missing `soundevents_test` / `nav_hulls` lines in the map compile log appear on a successful compile and do not block it.
- **Doesn't work:** fresh addon failed validation because of template `resource/flash3` (fixed, see BUG_LOG). `list_map_entities` returns every property of every entity (template map ≈ 5 KB of JSON) — heavy for context.
- **Rule:** code changes in `src/dota2_mcp/` take effect in the agent only after the MCP server restarts; test them directly via `.venv` Python meanwhile.

### 2026-10-22 — Test plan stage 0 (in-game part)
- **Works:** NetCon ping, `dota_launch_custom_game mcp_lab lab` → map loads to `CUSTOM_GAME_SETUP`; `script_reload` re-inits the VM; no Lua errors.
- **Noise:** `errors_and_warnings` is full of harmless base-game lines (missing stock `.vmat_c`/`.vpcf_c`, `world_visibility.vvis_c` with `-nolightmaps`, Steam asserts, UTF-16 perf warning, missing `addon_russian.txt`). Only lines from `scripts/vscripts` / `Script Runtime Error` matter.
- **Gotcha:** `console.log` on disk lags behind NetCon output by a few seconds; prefer the NetCon response right after a command.

### 2026-10-22 — Test plan stage 1 (Lua ability `mcp_frost_nova`)
- **Works:** `get_base_dota_definition` (crystal nova values), `search_dota_assets`, `inspect_particle` (reports CP1 only — semantics such as radius/duration still have to be guessed from the stock ability), `search_sound_events`, `verify_vscript_api`, `upsert_localization`, `validate_and_sync_precache`. In-game autotest (Lua casts the ability on spawned creeps, checks HP + modifier, prints PASS/FAIL) passed. Hot reload: edit Lua → `script_reload` → re-run autotest via a `Convars:RegisterCommand` console command → new code is used, no relaunch needed.
- **Doesn't work:** `validate_and_sync_precache` only finds literal `.vmdl/.vpcf/.vsndevts` paths; sound events used by name (`EmitSound*("Hero_X.Y")`, `AbilitySound`) are NOT resolved to their `.vsndevts`, so the sound file is not precached.
- **Workaround:** add a `"precache" { "soundfile" "soundevents/...vsndevts" }` block to the ability KV (the file name comes from `search_sound_events`).
- **Search tips:** `search_dota_assets` returns econ (cosmetic) variants first; add the hero folder to the query (`hero_crystalmaiden/maiden_crystal_nova`). `search_sound_events` matches substrings of the event name: `CrystalNova`, not `Crystal_Nova`.
- **Cost traps:** `read_latest_console_log` with a large `tail_lines` (400) dumps tens of KB of engine noise — use ≤ 60 or rely on the NetCon response. Each `verify_vscript_api` call re-runs `script_help2`, adding ~3,600 lines to `console.log`, and returns duplicate matches from earlier dumps. Custom-game launch with `wait_response_ms` ≥ 15000 is enough for the game to reach `PRE_GAME`.
- **Autotest pattern:** expose a console command from the game mode (`Convars:RegisterCommand`) that spawns targets, casts via `CastAbilityOnPosition`, and prints `AUTOTEST ... PASS/FAIL`; the agent runs it via `run_console_command` and reads the result directly from the NetCon response.

### 2026-10-22 — Context cost optimization (log + VScript API)
- **Done:** `verify_vscript_api` now uses a per-build cache: first call ≈ 2.5 s (one `script_help2` dump read from `console.log`), later calls ≈ 0 s, offline, no console pollution, compact deduplicated output. Console output is noise-filtered: default `read_latest_console_log` ≈ 2–3 K chars instead of ≈ 30 K for `tail_lines=400`.
- **Rule:** changes to `src/dota2_mcp/` reach the agent's MCP tools only after the MCP server restarts (new session); until then test via `.venv` Python scripts.
- **Gotchas:** NetCon response lines have no `[VScript]` channel tag, `console.log` lines do — noise regexes must accept both. Enum lines in the dump are mixed-case (`DOTA_ModifyGold_*`, `k_ECustomCameraEventFlags_*`). There is no `script <lua>` console command, and `;` splits console commands — expose debug helpers via `Convars:RegisterCommand`, registered at file top level so `script_reload` adds new ones without relaunch.

### 2026-10-22 — Units spawned from Lua are invisible without precache
- **Symptom:** creeps from `CreateUnitByName` exist (found via `FindUnitsInRadius`, take damage) but the player cannot see them.
- **Fix:** `PrecacheUnitByNameSync("<unit_name>", context)` in `Precache`. `validate_and_sync_precache` does not do this yet (idea logged).

### 2026-10-22 — Stock hero innates affect custom abilities
- **Symptom:** creeps hit by the ice ability `mcp_frost_nova` showed fire on them.
- **Cause:** Lina's innate `lina_slow_burn` turns any magic damage dealt by Lina into a burn (`modifier_lina_slow_burn`), custom Lua abilities included. Confirmed by listing modifiers via the `mcp_lab_status` debug command.
- **Rule:** when testing a custom ability on a stock hero, check the hero's innate/passives (`get_base_dota_definition` hero → `Innate "1"` abilities) and remove them, or use a custom hero. A debug command that prints modifiers on units is the fastest way to explain unexpected visuals.

### 2026-10-22 — Test plan stage 2 (custom hero `mcp_frost_mage`)
- **Works:** hero override per Valve's `addon_template`: entry with any name + `"override_hero" "npc_dota_hero_crystal_maiden"`; `MovementSpeed`/`ArmorPhysical` overrides apply. `inspect_model` gave real attachments (`attach_attack1` on the staff) and cast activities (`ACT_DOTA_CAST_ABILITY_1/2/4`; CM has no `_3`). Tracking projectile (`ProjectileManager:CreateTrackingProjectile` + `OnProjectileHit`), stun via `CheckState`, aura via `IsAura`/`GetModifierAura`, ultimate via `CreateModifierThinker` + `StartIntervalThink` — all PASS in the in-game autotest. 18 Lua names verified offline from the API cache in ~1 s.
- **Doesn't work:** `"AbilityN" ""` in `npc_heroes_custom.txt` does not clear a slot — the engine compacts the list and the ultimate shifts to slot 4.
- **Solution / Rule:** fill unused slots with hidden placeholder abilities (`ability_datadriven`, `DOTA_ABILITY_BEHAVIOR_HIDDEN | PASSIVE | NOT_LEARNABLE`, `MaxLevel 0`). Log `GetAbilityByIndex` at spawn to verify the layout. Stock helper abilities (e.g. `crystal_maiden_freezing_field_stop`) and talents stay after the override.
- **Cost traps:** `search_dota_assets` with a broad query + `limit 60` returns ≈ 12 KB; query the exact effect name (`hero_crystalmaiden/maiden_frostbite`) with `limit ≤ 6`. `get_base_dota_definition` for a hero returns ≈ 10 KB (bot builds, item slots, talents) — a compact mode is worth adding.

### 2026-10-22 — Custom minimap without Hammer
- **Works (per Valve wiki "Level Design/Dota/Minimap"):** two `dota_minimap_boundary` entities (opposite corners; Z delta = capture depth) added via `add_map_entity` → `disconnect` → `compile_addon_resource` map → launch → `dota_minimap_create` (cheat command, works in Tools mode). The game writes `content/.../materials/overviews/<map>.tga/.txt/.vmat`, compiles them, and writes `game/.../resource/overviews/<map>.txt` (`pos_x`, `pos_y` = top-left corner, `scale` = world units per pixel at 512 px). The minimap appears after relaunching the map.
- **Gotcha:** visible units and lingering particles are baked into the image — remove units and park the hero outside the bounds first (`mcp_lab_minimap_prep` debug command). `GetWorldMin/MaxX/Y` return engine limits (±16352), not the ground size.
- **Bug fixed:** a map compile while the game has that map loaded fails to write the VPK but exits 0 (see BUG_LOG).

### 2026-10-22 — Training dummies for tests
- **Doesn't work:** `npc_dota_target_dummy` from `npc_units.txt` → "Cannot create an entity because entity class is NULL".
- **Works:** `npc_dota_hero_target_dummy` set up like Valve's `hero_demo` (`SetAbilityPoints(0)`, `Hold()`, `SetIdleAcquire(false)`, `SetAcquisitionRange(0)`, team `DOTA_TEAM_NEUTRALS`), precached with `PrecacheUnitByNameSync`. It keeps full HP, so damage checks use a Lua modifier counting `MODIFIER_EVENT_ON_TAKEDAMAGE` instead of HP.

### 2026-10-22 — Hero display name with override_hero
- **Rule:** the HUD shows the localized name of the overridden hero; add the token `npc_dota_hero_<base>` (e.g. `npc_dota_hero_crystal_maiden`) to the addon localization files to rename it.

### 2026-10-22 — Test plan stage 3 (waves, spawners, AI, elite)
- **Works:** `info_target` spawn points via `add_map_entity` + `disconnect` + map recompile, found in Lua with `Entities:FindByName`. Custom creatures (`npc_dota_creature`) reusing stock models, recolored with `SetRenderColor`; AI as a Lua modifier thinking every 0.5 s (`FindUnitsInRadius(..., FIND_CLOSEST)`, `MoveToTargetToAttack`, `CastAbilityNoTarget(ability, -1)`); telegraphed slam via `OnAbilityPhaseStart` (warning ring for the cast point) + `OnAbilityPhaseInterrupted` cleanup; timed waves via `SetContextThink`. In-game autotest PASS.
- **False PASS trap:** the first run "passed" while the AI modifier was not attached — creatures auto-acquire and chase by themselves. Assert the mechanism (`HasModifier("modifier_mcp_wave_ai")`), not only the outcome.
- **API cache gap:** global constants such as `FIND_CLOSEST` (=1), `FIND_UNITS_EVERYWHERE` (=-1), `DOTA_UNIT_ORDER_*` (e.g. `ATTACK_TARGET`=4) and the method `IsNull` are absent from the `script_help2` dump, yet exist at runtime. "No match" in `verify_vscript_api` is not proof of absence — confirm such names live (print them from a debug command).
- **Open question:** "Attempted to create unknown modifier type modifier_mcp_wave_ai!" is printed once per unit, but the server has the modifier and the AI works; most likely the client VM side. Cause not found yet.
- **Cost traps:** `compile_addon_resource` returns ≈ 6 KB (repeated shader warnings) per map build; filter like the console.

### 2026-10-22 — Test plan stage 4 (custom item `item_mcp_void_shard` with own icon)
- **Works:** `item_lua` item with intrinsic passive modifier (stats via `MODIFIER_PROPERTY_*`), point-target active, horizontal motion controller pull (`LinkLuaModifier(..., LUA_MODIFIER_MOTION_HORIZONTAL)`, `ApplyHorizontalMotionController`, `UpdateHorizontalMotion`, `RemoveHorizontalMotionController` on destroy), stock `modifier_silence`. In-game autotest PASS. Icon drawn procedurally (pure-Python PNG, 88×64) — `examples/mcp_lab/tools/draw_void_shard_icon.py`.
- **Icon pipeline (fixed, see BUG_LOG):** PNG goes to `content/<addon>/panorama/images/items/<name>.png`, item uses `"AbilityTextureName" "item_<name>"`; the icon is compiled as a dependency of a Panorama layout that references it (`validate_and_sync_precache` now generates `mcp_auto_icons.xml`). Neither `resourcecompiler -i icon.png` nor Tools-mode on-demand loading compiles it.
- **Bug fixed:** `get_base_dota_definition` failed for all items (CRLF in items.txt).
- **Not in the API dump but exists:** `Vector:Normalized()`, built-in modifier names like `modifier_silence` (verified live by the autotest).
- **Noise filter works in practice:** a full custom-game launch response dropped from ≈ 30 lines of engine chatter + 20 false "errors" to only meaningful lines (`noise_lines_hidden` ≈ 180).

### 2026-10-22 — Stage 4 playtest feedback (owner)
- **Shop:** a custom item is only findable via search until it is listed in `scripts/shops.txt`. An addon `shops.txt` REPLACES the stock one, so start from the stock `scripts/shops.txt` (extract from VPK) and add the item to a category (`misc` = "Разное").
- **Looping sounds:** `Hero_Enigma.Black_Hole` loops; emitted via `EmitSoundOnLocationWithCaster` it can never be stopped and played forever. Rule: emit looping/long stock sounds on an entity you control (a `CreateModifierThinker` thinker) and `StopSoundOn` it in the modifier's `OnDestroy`. Same for long stock sounds reused for shorter spells (CM's 10 s `freezingField.wind` on a 3 s custom ultimate).
- **Autotests must not run on game start:** they polluted manual playtests (casts, creeps appearing/disappearing). Run them only via console commands from the agent.
- **Debuffs on enemies are hard to see:** for player-facing checks of silence/disarm etc., add a demo command where an enemy applies the effect to the player's hero (`mcp_lab_demo_silence`).
- **Note:** a hero created with `CreateUnitByName` (no player owner) can cast items via `CastAbilityOnPosition(pos, item, -1)`.

### 2026-10-22 — Test plan stage 5 (Panorama HUD "The Rift")
- **Works:** `content/<addon>/panorama/layout/custom_game/custom_ui_manifest.xml` with `<CustomUIElement type="Hud" layoutfile="file://{resources}/layout/custom_game/<hud>.xml" />` (pattern from Valve's Overthrow); `compile_addon_resource` on the manifest builds the whole chain (`.vxml_c`, `.vcss_c`, `.vjs_c`). Lua→JS via `CustomGameEventManager:Send_ServerToAllClients`, JS→Lua via `GameEvents.SendCustomGameEventToServer` + `CustomGameEventManager:RegisterListener`; no event declaration file needed. `#tokens` in Panorama resolve from `resource/addon_<lang>.txt`. Autotest proves both directions: Lua sends a `ping`, JS echoes it back.
- **JS API reference:** `cl_panorama_script_help_2` prints all Panorama JS bindings (~16 K lines, 2 169 signatures) and NetCon returns it completely — cached like the Lua API (idea logged). Also available: `cl_panorama_typescript_declarations`, `dump_panorama_css_properties`, `dump_panorama_events`, `panorama_print_cache_status` (which Panorama files are loaded — the fastest way to see whether your HUD is loaded at all).
- **Don't include `dotastyles.css`:** standalone `resourcecompiler` fails with `File does not exist "panorama/styles/dotastyles.css"` (stock CSS has no source in the SDK).
- **Write order matters in Tools mode:** the running game watches `content/` and recompiles on save. Writing the manifest before the layout it references made the on-demand compile fail; the game then silently kept the stock manifest from `pak01` for the session. Write child files (layout/css/js) first, the manifest last; if it already happened, re-save the manifest (triggers "Panel CustomUI is reloading layout") and relaunch the map.
- **Events and hot reload:** `ListenToGameEvent` registrations SURVIVE `script_reload` and STACK (an `entity_killed` handler ran 4× after 3 reloads). Register at file load, keep the id on `GameRules` and `StopListeningToGameEvent(old_id)` first. Assert exact counts (`== before + 1`) to catch this.
- **`ForceKill()` did not raise `entity_killed`** for `npc_dota_creature` units, and `MODIFIER_EVENT_ON_DEATH` on the dying unit did not fire either; killing with `ApplyDamage` raises `entity_killed` reliably (Valve's Overthrow also uses `entity_killed`).

### 2026-10-22 — Commit messages from PowerShell
- **Doesn't work:** `git commit -F - @'...'@` in Windows PowerShell 5.1 — the here-string is passed as a pathspec, not stdin.
- **Solution / Rule:** write the message to a temp file and use `git commit -F <file>`.
