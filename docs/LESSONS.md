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

### 2026-10-22 — Commit messages from PowerShell
- **Doesn't work:** `git commit -F - @'...'@` in Windows PowerShell 5.1 — the here-string is passed as a pathspec, not stdin.
- **Solution / Rule:** write the message to a temp file and use `git commit -F <file>`.
