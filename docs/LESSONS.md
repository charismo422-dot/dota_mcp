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
- **Resolved (stage 5b):** "Attempted to create unknown modifier type ..." came from the CLIENT VM: `addon_game_mode.lua` runs only on the server, so `LinkLuaModifier` calls there are unknown to the client (no effect particles, buff icons, tooltips). Put such links in a shared file `require`d both by `addon_game_mode.lua` and by an ability script (ability/item scripts load on the client too).
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

### 2026-10-22 — Stage 5b (world-space Panorama: damage numbers, overhead charges, NPC dialog)
- **Works:** one full-screen click-through Hud layout, JS loop via `$.Schedule(0, Tick)`; anchor = `Entities.GetAbsOrigin(ent)` + `Entities.GetHealthBarOffset(ent)` → `Game.WorldToScreenX/Y`; multiply by `1080 / Game.GetScreenHeight()` (screen pixels → Panorama layout units) and set `panel.style.position = "Xpx Ypx 0px"`. Floating numbers: `$.CreatePanel("Label", ...)`, per-frame rise/fade/pop via `style.opacity` / `style.preTransformScale2d`, `DeleteAsync(0)`. Damage events come from a Lua `MODIFIER_EVENT_ON_TAKEDAMAGE` (amount + `damage_type` for color). NPC dialog: server proximity check → open/reply/close events; typewriter text; options are Buttons with `SetPanelEvent("onactivate")`. Glass look: `background-blur: gaussian(6)`, translucent background, thin light border, soft `box-shadow`.
- **Autotest pattern for UI:** the JS answers a `probe` event with what it shows (counts/flags); `autochoose` events call the same function as a mouse click. Proves rendering logic + both event directions without screenshots.
- **Tools mode compiles Panorama on save** (`compile_addon_resource` then reports `[SKIP]`, identical CRC) — still write children before the manifest.
- **Playtest convenience:** `GameRules:SetStartingGold(99999)` in the test addon so new shop items can be bought by hand.

### 2026-10-22 — Test plan stage 6 (map dressing with point entities)
- **Works:** `ent_dota_tree` (with `model`, e.g. `models/props_tree/tree_pine_01_heavysnow.vmdl`), `ent_dota_shop` (shopkeeper model, `shoptype`), `prop_dynamic` (`model`, `rendercolor`, scales) via `add_map_entity`; `remove_map_entity` by targetname; `disconnect` → recompile → relaunch. Runtime checks: `Entities:FindAllByClassname("ent_dota_tree")`, `GridNav:IsNearbyTree` (trees are NOT `GridNav:IsBlocked`), `tree:CutDown(-1)` / `IsStanding()` / `GrowBack()`.
- **Entity reference on disk:** `game/dota/dota.fgd` (+ `game/core/base.fgd`) is Valve's authoritative list of map entities and their keys — read it instead of guessing. Most addon `.vmap` files are binary DMX (79 of 82 here) and stock maps put trees/shops inside prefabs, so copying from existing maps rarely works.
- **Shop needs a radius:** `ent_dota_shop` is only the shopkeeper building; the purchase area is a `trigger_shop` BRUSH (cannot be created with point-entity tools). From Lua: `SpawnDOTAShopTriggerRadiusApproximate(origin, radius):SetShopType(DOTA_SHOP_HOME)`. `IsInRangeOfShop` updates only on the next physics tick after teleporting — check with a short delay.
- **Batching:** 25 map edits through single MCP calls is slow and context-heavy; a batch call (or calling `vmap_builder.add_map_entity` from a script) is much cheaper (idea logged).
- **Tint:** `prop_dynamic` `rendercolor` is applied (GetRenderColor = 190 90 255), yet the cavern crystal material ignores it — not every model's material supports tinting; check visually.

### 2026-10-22 — Stage 5b/6 playtest feedback (owner) and fixes
- **NPC models:** hero models (`models/heroes/oracle/oracle.vmdl`) on `npc_dota_creature` look naked (cosmetics are separate wearable models) and frozen. Use complete creature/neutral models that have `ACT_DOTA_IDLE` (check with `inspect_model`), e.g. `n_creep_frostbitten_shaman01.vmdl`; tint with `SetRenderColor`. Keep NPCs away from props (the keeper first spawned inside a crystal).
- **Solid props:** `prop_dynamic` does not block Dota pathing. Add `point_simple_obstruction` entities (dota.fgd) — one per 64-unit GridNav cell, e.g. center + 4 neighbours for a large prop. Check with `GridNav:IsBlocked(pos)` (stays `IsTraversable() == true`).
- **Secret shop for tests/custom games:** `SpawnDOTAShopTriggerRadiusApproximate(pos, r):SetShopType(DOTA_SHOP_SECRET)`. Two shop triggers on the same spot do NOT stack — a unit counts as being in only one; give each shop its own non-overlapping radius (second shopkeeper `secretshopkeeper_dire.vmdl`).
- **Typewriter text:** frame-based typing (2 chars/frame) is ~280 chars/s on a high-FPS client and words jumped between lines while typing. Use time-based speed (~35 chars/s) and lay out the whole line from the start: `html="true"` label, untyped tail wrapped in `<font color='#00000000'>`. Show options after typing ends; click on the text skips typing.
- **Panorama pauses when Dota is not the foreground window:** `$.Schedule(0, ...)` loops ran 6 frames in 6 s while `Game.Time()` advanced. Autotests of client UI must not rely on per-frame animation finishing (use skip paths) and report `frames` to detect this.
- **JS hot reload duplicates:** each on-save recompile re-runs the layout script ("world UI script loaded" several times) — old instances can keep subscriptions; relaunch the map before trusting UI autotests.

### 2026-10-22 — Stage 6 playtest feedback #2 (NPC animation, overlaps, context cost)
- **Static NPC animation:** a `npc_dota_creature` with `DOTA_UNIT_CAP_MOVE_NONE` plays its spawn animation and then freezes. Drive idle from script (`StartGesture(ACT_DOTA_IDLE)` every few seconds, sometimes `ACT_DOTA_IDLE_RARE`), turn to the speaker with `FaceTowards`, play a talk/cast gesture on dialog open and on the reward. Visual result still to be confirmed by the owner.
- **Shopkeeper models:** `secretshopkeeper_dire.vmdl` has no animations at all (`inspect_model` → empty activities). Use `models/heroes/shopkeeper_dire/shopkeeper_dire.vmdl` / `shopkeeper/shopkeeper.vmdl` (`ACT_DOTA_IDLE`). Always `inspect_model` an NPC/shop model for `ACT_DOTA_IDLE` before using it.
- **Never let props overlap:** `add_map_entity` now returns `overlap_warning` when a model entity lands within 250 units of another model entity (caught the shopkeeper-inside-crystal case: 71 units). There is no "move" tool yet: remove + add.
- **Context cost (why limits burn fast):** the biggest cost is the conversation itself — every turn re-sends the whole history, and this session is very long. Per-call waste found and cut: map compile response ≈ 6 K → 0.5 K chars (benign SDK lines hidden, log tail only on failure); launch response loses the `PR:*` / game-state lines; the 600-char hero slot print was removed. Rule: start a NEW chat per stage / feature — `.private/STATUS.md`, `docs/LESSONS.md` and memory carry the knowledge over cheaply.

### 2026-10-22 — Commit messages from PowerShell
- **Doesn't work:** `git commit -F - @'...'@` in Windows PowerShell 5.1 — the here-string is passed as a pathspec, not stdin.
- **Solution / Rule:** write the message to a temp file and use `git commit -F <file>`.

### 2026-10-23 — Test plan stage 7 (stock + custom sounds)
- **Works (custom sound pipeline):** `.wav` (16-bit mono 44.1 kHz, generated with Python `wave`) in `content/<addon>/sounds/<dir>/x.wav`; own `content/<addon>/soundevents/<name>.vsndevts` in the same KV3 text format as Valve's decompiled files (header `<!-- kv3 encoding:text:version{e21c7f3c-...} format:generic:version{7412167c-...} -->`, unquoted `Name.Event = { type = "dota_src1_2d" | "dota_src1_3d", volume, pitch, vsnd_files = "sounds/<dir>/x.vsnd" }`); compile; `PrecacheResource("soundfile", "soundevents/<name>.vsndevts", context)`; `EmitGlobalSound` / `EmitSoundOn` play it. Types seen in stock files: `dota_src1_2d` (UI/global), `dota_src1_3d` (positional, with `soundlevel`, `distance_max`).
- **Gotcha:** compiling the `.vsndevts` does NOT compile the referenced `.wav` (fixed in `compile_addon_resource`, see BUG_LOG). A `.wav` compiles directly to `sounds/.../x.vsnd_c`.
- **Live check without ears:** `entity:GetSoundDuration("Event", "")` returns the real audio length for a loaded event (1.080 s / 0.450 s matched the synthesized files) and `-1` for an unknown event — a cheap autotest that the event and its audio are loaded.
- **Decompiling all stock soundevents is cheap:** `Source2Viewer-CLI -i pak01_dir.vpk -f soundevents/ -e vsndevts_c -d --threads 8 -o <dir>` → 946 files, 24 MB, ~2 s. Used for the cached name → file index (~105 K events, mostly VO).
- **Precache by name works:** `validate_and_sync_precache` now adds the `.vsndevts` of every event name found in Lua/KV and flags typos in `EmitSound*` calls (tested: `Hero_Crystal.CrystalNovva` → `unknown_sound_events`).
- **Log noise:** `read_latest_console_log(only_errors=True)` was full of client start-up lines (team fandom images, `*_staging.vdata_c`, `soundevents_test`); added to the noise filter (takes effect after the MCP server restarts).


### 2026-10-23 — Test plan stage 8 (localization RU/EN)
- **Works:** `resource/addon_<lang>.txt` (UTF-16 or UTF-8) serves both tooltips and Panorama `#tokens`; `panorama/localization/addon_*.txt` is NOT needed (its "failed to load" log line is harmless, now filtered). Tooltip variables follow the stock files: `%value%` from `AbilityValues`, `%%` = percent sign, modifier descriptions use `%dMODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE%` (value from the Lua modifier, needs the modifier linked on the client). `_Lore` and `_NoteN` keys work like in stock `abilities_english.txt`.
- **Autotest pattern:** Lua builds the token list from its own KV (`LoadKeyValues` of abilities/items/units) + UI/dialog/modifier names and sends it to Panorama; JS checks each with `$.CanLocalize("#x")` and answers with `$.Language()`, the unresolved list and what the HUD title shows. A control token that does not exist must come back unresolved — otherwise a broken probe would "pass". Panorama JS API dump: `cl_panorama_script_help_2` goes to NetCon only, not to `console.log` — capture it via `_send_netcon_raw`.
- **Language switch:** `cl_language english` at runtime changes nothing (not even after relaunching the map) — the UI language is fixed when Dota starts. Switch via Steam (Dota 2 → Properties → General → Language), then restart Dota (owner confirmed: RU and EN both shown correctly). Restore `cl_language` if you touch it: it is an archived convar.
- **Log noise:** `DOTA_Tooltip_Ability_<name>_SummaryDescription` "failed to localize" — the HUD looks it up for every ability, but no stock ability has it either; harmless (filtered). Engine warns UTF-16 localization files load slower than UTF-8 (perf only).
- **Validator:** `validate_and_sync_precache` now has a `localization` section; it found `addon_game_name` missing in Russian on the first run.

### 2026-10-25 — Test plan stage 9 (enemy stock heroes under Lua AI)
- **Works:** stock heroes from `CreateUnitByName("npc_dota_hero_sven", pos, true, nil, nil, DOTA_TEAM_BADGUYS)` with no owner: `HeroLevelUp(false)` loop, `SetAbilityPoints(0)` + `ability:SetLevel`, `AddItemByName`, `SetRespawnsDisabled(true)`, `PrecacheUnitByNameSync` for each hero. AI = Lua modifier thinking every 0.25 s, all actions are orders (`CastAbilityOnTarget/OnPosition/NoTarget(ab, -1)`, `MoveToTargetToAttack`, `MoveToPosition`); retreat state by `GetHealthPercent()` with a fast-regen property while retreating. Boss: `MODIFIER_PROPERTY_MIN_HEALTH` = 1 until phase 3 ends, phase change telegraphed by a 1 s rooted+disarmed modifier with the Lina ring particle (CP1 = radius, 0, 1/duration). `entity_killed` gives the killer via `entindex_attacker`; kills via `ApplyDamage` are reported reliably. Autotest PASS 18/18 on the first run.
- **Stock names:** ability names via `get_base_dota_definition` hero blocks; item names taken from the same block's bot `Loadout` (proven real). Cost ≈ 3–4 K tokens per hero — query only the heroes you use.
- **Scope trap (BUG_LOG):** `addon_game_mode.lua` globals (the game mode class) are invisible to files loaded with `require`. Return a table of methods from the module and merge it in `addon_game_mode.lua`.
- **AI test trick:** give the player's hero stock `modifier_invulnerable` during the AI check — `FindUnitsInRadius` without the invulnerable flag skips it, so the AI picks the training dummies (NEUTRALS heroes, enemies of BADGUYS). Remove it to test the player's death on purpose; `RespawnHero(false, false)` brings the hero back at once.
- **Step sequencing:** chained `SetContextThink` steps need unique think names; re-using one name inside its own callback and returning `nil` cancels the newly scheduled step.
- **Harmless noise:** "Trying to create Projectile From npc_dota_hero_target_dummy Missing Attachment attach_attack1" — dummies forced to attack by Axe's Berserker's Call.
- **Log tool gap (BUG_LOG):** `read_latest_console_log` errors include earlier launches; check they come after the latest launch marker.
- **Russian client keeps English hero names** (`$.Localize("#npc_dota_hero_lina")` → "Lina").

### 2026-10-25 — Stage 9 follow-up (smarter hunter AI, stock items by orders)
- **Works:** item names/behaviors via `get_base_dota_definition` (`item_blink` POINT, `item_force_staff` UNIT_TARGET 150 mana, `item_faerie_fire` / `item_arcane_boots` / `item_blade_mail` IMMEDIATE NO_TARGET); `FindItemInInventory(name)` + `IsFullyCastable()` covers cooldown and mana; cast with the same `CastAbility*` orders as spells. Faerie Fire is consumed (`HasItemInInventory` false after use).
- **One item order per think:** two orders in the same tick overwrite each other; return after each item use.
- **Force Staff on self pushes the way the hero faces;** `SetForwardVector` right before the cast does not stick while the hero turns. Order a move to the escape point and cast once `DotProduct(GetForwardVector(), dir) > 0.9`. Pointless closer than ~300 to the destination (test must place the hero far from home).
- **Kiting:** `MODIFIER_EVENT_ON_ATTACK` (`params.attacker == parent`) marks the attack; next think steps back to target − dir × (kite+150) for ≤ 1 s. Measured gain ≈ 280–300.
- **Training dummies heal back to full at once** — HP-based target choice cannot be tested on them; spawn a stock hero (NEUTRALS, `SetIdleAcquire(false)`, `Hold`) with 30 % HP a bit further than the dummies.
- **Reaction delay** (`RandomFloat(0.3, 0.6)` after each order, retreat/return exempt) keeps the stage 9 timings: all old checks still PASS.
- **Repeat-run trap (BUG_LOG):** after `RespawnHero` the hero stands in the fountain with `modifier_fountain_invulnerability`; test kills need `DOTA_DAMAGE_FLAG_BYPASSES_INVULNERABILITY`. Run every autotest twice in a row.

### 2026-10-25 — Test plan stage 10 (cutscene "The Rift Awakens")
- **Works (camera):** Lua owns the camera — `CreateModifierThinker` (needs a Lua modifier, any empty one) + `PlayerResource:SetCameraTarget(pid, thinker)`, thinker moved every 1/30 s with `SetAbsOrigin` (smoothstep path hero → rift → hero); return = `SetCameraTarget(pid, nil)` + `CenterCameraOnUnit`. Zoom: Lua sends an event, JS lerps `GameUI.SetCameraDistance` (stock 1134). `AddFOWViewer` at the far point, the thinker has no vision. Check: JS `GameUI.GetCameraLookAtPosition()` reported back to Lua.
- **Works (HUD):** `$.GetContextPanel()` is the layout's own CustomUIElement; walk `GetParent()` to the top, `FindChildTraverse("HUDElements").visible = false` hides the whole stock HUD; the other custom layouts are the siblings of the context panel in `CustomUIContainer_Hud`. Restore exactly the panels you hid.
- **Works (slides):** own 1920×1080 `.png` in `content/<addon>/panorama/images/custom_game/...` — `validate_and_sync_precache` compiles them (no size limit seen); `<Image src="file://{images}/custom_game/cutscene/x.png" scaling="stretch-to-cover-preserve-aspect">`; zoom-in = per-frame `style.preTransformScale2d`, shake = per-frame `style.position` offset on the parent frame; crossfade via `.Shown` class + opacity transition. Art generated with Pillow (`examples/mcp_lab/tools/make_lab_cutscene.py`).
- **Sound:** 40 s `.wav` → `GetSoundDuration` = 40.000 exactly, the scene length is taken from it. **`.mp3` compiles directly** (`sounds/x.mp3` referenced as `x.vsnd` in `.vsndevts`, made with ffmpeg; `GetSoundDuration` 2.221). Stop on skip: `StopGlobalSound(event)` (not measurable from Lua — owner checks by ear).
- **Invulnerability:** own modifier with `INVULNERABLE`, `COMMAND_RESTRICTED`, `NO_HEALTH_BAR`. `COMMAND_RESTRICTED` blocks only the player's orders — a Lua `MoveToPosition` still moved the hero; added `ROOTED` + `DISARMED`.
- **Hold-to-skip:** `Game.AddCommand("+cmd"/"-cmd")` + `Game.CreateCustomKeyBind("SPACE", "+cmd")` gives press/release; JS sends the held time, Lua accepts ≥ 1 s. Console commands outlive the script ("Cannot create ConCommand ... already exists" after a layout reload or map relaunch) and keep pointing at the dead script: use a fresh random command name on every load.
- **Root panel of a layout must not have an `id`** ("Found root panel with 'id' attribute, which is not permitted"); the failed compile makes the game keep the old manifest — fix, then re-save the manifest.
- **Panorama hot reload is not trustworthy for timing tests:** after saving a `.js` mid-session the layout reloads, but the old context kept answering probes and the per-frame loop did not animate (zoom/shake/subtitles stuck). Relaunch the map (`dota_launch_custom_game`) after Panorama edits before an autotest.
- **Screenshots (agent eyes):** `jpeg_screenshot <name> <quality>` over NetCon writes `game/dota/screenshots/<name>_NNNN.jpg` even when the Dota window is not focused (also `png_screenshot`, `screenshot`). New MCP tool `take_game_screenshot`. It caught a bug the probe missed (custom layouts still visible) — look at a frame for anything visual.
- **Autotest 24/24 PASS twice in a row**; `mcp_lab_cutscene [start second]` demo (start at 32 to see only the ending).

### 2026-10-25 — Test plan stage 11 (game flow: lobby, lives, respawn, end screen)
- **Works (lobby):** own `<CustomUIElement type="GameSetup">` replaces the stock team select; `GameRules:SetCustomGameSetupAutoLaunchDelay(15)` gives the countdown, the host starts early with JS `Game.SetAutoLaunchEnabled(false)` + `Game.SetRemainingSetupTime(1)` (pattern from Valve's `content/dota/panorama/scripts/custom_game/team_select.js`). Host flag on the client: `Game.GetLocalPlayerInfo().player_has_host_privileges`; non-hosts get `button.enabled = false`. JS only asks (`mcp_lab_lobby_set`), Lua decides: `GameRules:PlayerHasCustomGameHostPrivileges(PlayerResource:GetPlayer(pid))` + state `CUSTOM_GAME_SETUP` + value whitelist, then `CustomNetTables:SetTableValue` (table declared in `scripts/custom_net_tables.txt`, KV3 like Valve's `conquest`); every client shows the value via `SubscribeNetTableListener`. Lua console commands work during the lobby, so the agent tests it there (`mcp_lab_lobby_test`), holding the lobby with `SetCustomGameSetupRemainingTime(-1)`.
- **Works (flow):** `SetCustomGameForceHero` + `SetHeroSelectionTime(0)`, `SetStrategyTime(0)`, `SetShowcaseTime(0)`, `SetPreGameTime(0)` → hero-select and pre-game last 0.03 s (measured with `game_rules_state_change` + `Time()`). `GameModeEntity:SetFixedRespawnTime(5)` → `GetTimeUntilRespawn()` 4.7 s 0.3 s after death, hero alive after 5 s. Model swap: `SetOriginalModel` + `SetModel` + `SetModelScale(0.6)` with Roshan (`inspect_model`: `attach_attack1`, `ACT_DOTA_CAST_ABILITY_1..3`), CM's projectile and abilities keep working; this custom game gives CM no `dota_item_wearable` children (0 found), the hide loop stays for heroes that have them.
- **Post-game kills server Lua:** after `SetGameWinner` no thinks, no custom-event listeners and no console commands run (`mcp_lab_status` prints nothing). Check everything server-side right after the call (it is synchronous), and let the EndScreen check itself in JS and print its own `$.Msg` line. Stats go into a net table BEFORE `SetGameWinner`; the EndScreen layout is created at post-game ("CreateGameEndScreen") and reads them at load.
- **Stock end UI:** `SetCustomVictoryMessage("")` keeps the stock "Victory of the Dark side" banner; `" "` (one space) + `SetCustomVictoryMessageDuration(0)` hides it. The post-game explosion particle is drawn OVER Panorama in the upper third of the screen — keep own end-screen text below ~y=330. A stock "Continue" button appears at the bottom.
- **Unfocused Dota = stale screenshots:** when Dota is not the foreground window the world and HUD are not redrawn (screenshots repeat the same frame with the clock at 0:00) and Panorama `$.Schedule` barely ticks, while events still work. For visual checks bring Dota to the foreground first (`SetForegroundWindow` with an Alt tap, see stage 11 session); autotest paths must not depend on `$.Schedule` timers.
- **Autotest 13/13 server + 6/6 end screen + 7/7 lobby PASS three launches in a row**, no Lua errors. Demo: lobby on every launch (host buttons), `mcp_lab_gameover [win]`, `mcp_lab_lives <n>` (0 = ∞).

### 2026-10-25 — Test plan stage 12 part 1 (stock map copy) + offline findings
- **Works:** stock map sources ship in `content/dota/maps/dota.vmap` (binary DMX, 63 MB; buildings live in prefab `maps/prefabs/dota_pvp_prefab.vmap`, resolved from `content/dota` at compile). `prepare_map_from_template(source_template="dota")` now finds it → keyvalues2 300 MB; `compile_addon_resource` 80 s (1025 resources, vpk 29 MB; 3 missing carnival models are harmless); `dota_launch_custom_game mcp_lab m1_dota` → `mcp_lab_autotest12_map` PASS (22 towers, 2 ancients, CM).
- **Fixed:** `shutil.move` of the 300 MB converted file failed with WinError 32 (copy done, unlink of temp blocked) → `os.replace` with retries. Unknown template names silently fell back to `template_map` → fallback only when `template_map` is asked. Timeouts: dmxconvert 600 s, map compile 1800 s.
- **No inline Lua from console:** `script <lua>` is "Unknown command" — put test code into a registered `Convars` command.
- **dota_683 / dota_685:** compiled old maps (patches 6.83/6.85) in `game/dota/maps/*.vpk`, no `.vmap` sources; inside `dota_683.vpk` the map is `maps/dota_683.vmap_c`, inside `dota_685.vpk` it is `maps/dota.vmap_c`. `search_dota_assets` does not see them (only `resource/overviews/dota_683.txt`). Launch not tested yet.
- **webm:** stock videos are loose files `game/dota/panorama/videos/**/*.webm` (not in vpk), used as `file://{resources}/videos/x.webm`; `<Movie>` attributes seen in stock layouts: `src`, `controls="none"`, `repeat="true"`, `autoplay="onload"`, `disableaudio`; JS `panel.SetMovie(url)`. Live test pending.
- **Russian voice:** `game/dota_russian/pak01_dir.vpk` holds only `sounds/vo/<hero>/` files (26 773, no soundevents) that replace the same paths → same event names (`crystalmaiden_cm_laugh_01`, `templar_assassin_temp_laugh_01`, `witchdoctor_wdoc_laugh_01`, `ursa_ursa_laugh_01`). Of CM/TA/Lifestealer/WD/Lion/Ursa: Russian exists for CM, TA, WD, Ursa; none for Lifestealer, Lion. Playback from Lua not tested yet.
- **Context cost:** broad `search_sound_events` ("_laugh_01", limit 200) and recursive listings of `content/dota_addons` cost ~10k tokens each — search exact names, list one folder.

### 2026-10-25 — Test plan stage 12 part 2 (live checks of parts 2, 4, 5, 6, 7)
- **Minimap of a stock map copy:** the minimap comes from `resource/overviews/<map>.txt`; a copied `dota.vmap` under a new name had none → grey minimap (owner). Fix: `prepare_map_from_template` now writes it from the stock `resource/overviews/<source>.txt` (stock materials reused). Screenshot: full minimap.
- **Part 2 (obstacles + zone):** `SpawnEntityFromTableSynchronous("point_simple_obstruction", {origin=pos})` → `GridNav:IsBlocked` true at all 5 points; point-in-polygon think + `modifier_knockback` (center = point beyond the hero) pulled the hero 756 → 406 from the center. HUD line: FAIL, see BUG_LOG (JS does not react to `mcp_lab_zone`).
- **Listeners at require time never fire:** `CustomGameEventManager:RegisterListener` in a module body (before Activate) is silently lost; register in InitGameMode or on first use (console then prints `Script_RegisterListener - Registered ...`).
- **Part 4 PASS:** `SetModelScale` lerp every 0.05 s for 3 s on `npc_dota_neutral_granite_golem`: 53 samples, 0.51 → 1.50, max step 0.022, monotonic.
- **Part 5 PASS:** `item_lua` with `AbilityTextureName "item_wraith_band"` (stock icon) + `item_recipe_*` (`item_datadriven`, `ItemCost 0`, `ItemRecipe 1`, `ItemRequirements "item_circlet;item_mantle"`) combines automatically; 7th item lands in backpack slot 6. Server Lua has no `item:GetAbilityTextureName()` — use `GetAbilityTextureNameForAbility(name)`.
- **Part 6:** own webm (0.2 MB and 29 MB, ffmpeg libvpx) placed loose in `game/dota_addons/<addon>/panorama/videos/` (no compile); playback not confirmed because the JS event did not arrive (same bug as part 2).
- **Part 7:** `EmitSoundOnClient("crystalmaiden_cm_laugh_01", player)` runs without errors; precache check missed dotless VO names → `validate_and_sync_precache` now also resolves dotless literals that are real event names (adds `soundevents/voscripts/game_sounds_vo_<hero>.vsndevts`). Russian audio — owner checks by ear.
- **Localization** strings added during a running session show as `failed to localize` until the next map launch.

### 2026-10-25 — Test plan stage 12 part 3 (fixes + recipe + old maps)
- **Zone HUD line / webm fixed:** after a fresh Dota restart the `mcp_lab_zone` / `mcp_lab_video` events reach JS (`$.Msg` in OnZone confirms); code also got a nil-hero guard and fallback knock-out directions (first free side outside the polygon). Zone autotest PASS, row shows "внутри" / "выход! откинут ×N"; stock, 0.2 MB and 29 MB webm play (screenshots). Exact root cause not isolated — likely the stale HUD JS of the running session.
- **Free recipe steals stock items:** `item_recipe_*` with `ItemCost 0` auto-combines Circlet + Mantle, so Null Talisman can never be built. Make the recipe paid (`ItemCost 150`) when parts are shared with stock items. Autotest checks "no combine before the recipe": PASS.
- **Autotest timing on maps with a lobby:** commands that use `HeroList:GetHero(0)` fail with nil until the lobby countdown ends (~15–25 s after launch) — wait for `game flow: lives=` in the log.
- **Old maps dota_683 / dota_685: do not use.** dota_683 crashed the client right after the match started; dota_685 was not found by name. Marked "не работает", not retried.

### 2026-10-25 — Test plan stage 13 (scaffold tool `scaffold_game_element`)
- **Works:** one call made `mcp_rift_quake` (point AoE: damage + stun + slow + heal, Leshrac particle + sound): KV block appended to `npc_abilities_custom.txt` (parsed with `vdf` before writing), Lua with `LinkLuaModifier` at the top of the ability file, RU title/description/value labels, `auto_precache.lua` got the particle literal and the sound's `.vsndevts` (resolved by name). In-game `mcp_lab_autotest13` PASS 7/7 on the first run, no Lua errors.
- **Guards work:** misspelled sound event and an already existing name are refused before anything is written.
- **Design choice:** the agent turns the owner's free-text description into a structured spec (kind, behavior, effects, values) — the tool does not parse prose. Standalone modifiers are linked in `mcp_scaffold_links.lua`, required by `addon_game_mode.lua` (server) and by every scaffolded ability file (client VM).
- **Test trap:** expected slow 30 % but the creep's speed fell 40 % — the Frost Mage's own frost aura adds 10 %. Check "slowed" as `<`, not an exact value, when the caster has auras.
- **Not checked in game:** `kind="item"` and `kind="modifier"`.
- **Log trap (known idea):** `read_latest_console_log(only_errors)` showed a Lua error from the previous session; confirm by timestamp against the last `Initializing game mode`.

### 2026-10-30 — Test plan stage 14 (stage 13 fixes: hotkey, particle size)
- **Runtime AddAbility has no hotkey:** it lands after the talents (index 20). Move it into an empty slot 0–5 with `SwapAbilities(empty, name, false, true)`; guard with `GetAbilityIndex() > 5`, otherwise a second run swaps it back (engine warns "trying to unhide in a slot > 5").
- **Particle size = CP1:** `leshrac_split_earth` reads CP1 (`inspect_particle` → `control_points_used [1]`); with CP0 only it is ~2x smaller than radius 325. `Vector(radius, radius, radius)` on CP1 fits. `scaffold_game_element` now emits it automatically when the particle reads CP1 and the spec has `radius`.
- **Live addon ≠ examples:** `examples/mcp_lab` is a git snapshot; the game runs `dota 2 beta/game/dota_addons/mcp_lab`. Edit/copy the live file before `script_reload`, otherwise the old code runs.
- **Screenshot timing:** bring Dota to the foreground first; `run_console_command(wait 900 ms)` then `take_game_screenshot` catches a 0.3 s-delayed cast with its particle.

### 2026-10-30 — mode-1 part 1 (private addon, offline build)
- **Works:** `create_or_configure_addon` + `prepare_map_from_template(source_template="dota")` + map compile (1m10s, same 3 harmless carnival models) give a fresh addon on a stock map copy. `scaffold_game_element` made 3 KV/Lua/RU skeletons (unit_target, point_aoe, passive) in one call each; their Lua was then rewritten by hand.
- **Scaffold trap:** `passive` always adds a default `bonus_damage 20` value even when the spec has other values — remove it by hand. The addon template ships a sample `templar_assassin_refraction_holdout` in `npc_abilities_custom.txt`.
- **Budget:** a whole mode chapter does not fit in one session — split into "code" and "in-game run + HUD" parts.

### 2026-10-30 — mode-1 part 1b (HUD + first in-game run)
- **`override_hero` keeps the template unit name:** a custom block `npc_dota_hero_<custom>` with `override_hero npc_dota_hero_tidehunter` spawns `npc_dota_hero_tidehunter`; `SetCustomGameForceHero("npc_dota_hero_<custom>")` logs `Unrecognized custom hero name` and no hero spawns. Force and match the template name.
- **Ability getters missing on the client VM:** `self:GetAbilityTargetTeam/Type/Flags()` in `CastFilterResultTarget` → client `Script Runtime Error` on every hover (server has them). Spell the KV constants out; `UnitFilter` exists on the client (`cl_script_help2 UnitFilter` checks the client API).
- **Walkers stuck:** a random point 1200 from a target may be off the walkable grid / far around cliffs (creep moved 7 units in 9 s). Pick a point with `GridNav:IsTraversable` and `GridNav:FindPathLength(pos, target)` in (0, 2500).
- **Stock map entities vary by timing:** a scan of `Entities` at game start may or may not see a stock spawned neutral boss yet; use the static spawner entity as the marker.
- **HUD via net table** (`SubscribeNetTableListener` + initial `GetTableValue`) worked on the first launch — no custom JS event, so the stage 12 bug did not apply.

### 2026-10-30 — mode-1 part 2a-1 (privacy, fixed zone)
- **Public repo hygiene:** private game-mode details (names, plot, ability names) go to `.private/`; public docs keep only technical lessons under a neutral name. Already pushed history keeps the old text — rewriting it needs a force push, so it is the owner's call.
- **Stock spawner entities are not in the `.vmap` copy:** `list_map_entities(classname_filter="roshan")` on a stock `dota.vmap` copy returns 0 — the spawner comes from a prefab/world layer. Take its origin from a runtime print (`Entities` scan) and hard-code it; remove it at runtime (`Entities:FindByClassname` + `UTIL_Remove`, repeated by a think).
- **Budget:** the session start (rules + context files + reading the stage 9 AI) already costs most of the context; `get_base_dota_definition(category="hero")` returns the whole hero file (~6k tokens) — prefer checking ability names in game by a print.


### 2026-10-31 — mode-1 part 2a-2 (AI packs, death rules, safety)
- **Stock spawner off for 10 game min:** `sv_cheats 1; host_timescale 10` for ~60 s real time — spawner removed once at start, no stock boss appears later. There is no `script <lua>` console command; check state with a registered debug convar.
- **Fountain invulnerability survives the respawn move (BUG_LOG):** a hero that respawns at the fountain and is moved by `FindClearSpaceForUnit` keeps `modifier_fountain_invulnerability` (seen stacked ×4); `FindUnitsInRadius` with no flags then skips it, so AI and creeps ignore the hero forever. Remove it in a loop (`while HasModifier do RemoveModifierByName end`) right after the move.
- **Timed schedule by `GameRules:GetDOTATime(false,false)`** in a 1 s think works under timescale (packs at 90/300 s, noise every 2–3 min, power +2/min).
- **Death rules / safety test:** `hero:Kill(nil, hunter)` fires `entity_killed` synchronously; `RespawnHero(false,false)` + `Kill` three times in one tick checks a "3 deaths / 60 s" rule instantly.
- **Solved (R2 2a-3) — AI observer ward:** spend the item (`RemoveItem`) and spawn the ward unit: `CreateUnitByName("npc_dota_observer_wards", pos, false, hero, hero, team)` + `modifier_kill {duration=360}`. The autotest checks the live ward unit, not only a counter. Was: `CastAbilityOnPosition(point, item_ward_observer, -1)` by an ownerless hero did not place a ward (item stays, charges 1, castable), even with the target off the hero and no overriding orders for 3 s. Next: read the cast error, or spawn `npc_dota_observer_wards` directly.
- **"Attempted to create unknown modifier type"** when `LinkLuaModifier` lives only in a server-required module — the client VM does not know the modifier; check whether harmless or link it where the client loads it too.
- **R2 2a-3:** "unknown modifier type" for the hunters fixed the same way as stage 5b: `LinkLuaModifier` moved from the server-only module into `mcp_scaffold_links.lua` (also loaded by the client through ability scripts). Rule: every new Lua modifier link goes there, not into a game-logic module.

### 2026-10-31 — mode-1 part 2-fix-1 (playable core, code only)
- **Zone by walkability:** precompute a grid (cell 96, radius 1900) once at start: a cell is in the zone when traversable and `GridNav:FindPathLength(pit, cell) <= path`; `InZone(pos)` is an O(1) lookup — cheap enough for a 0.1 s border think and for every damage event.
- **"Damage only from inside the zone":** `SetDamageFilter(function(ctx, e) return ctx:DamageFilter(e) end, self)`; return false when `entindex_attacker_const` is outside — covers attacks, spells and DoTs. The AI must walk in first, otherwise ranged hunters deal 0.
- **Border knockback toward the last inside point** (not the pit center) — the center can be behind a wall.
- **Debug unit-target abilities with a real order** (`CastAbilityOnTarget`) — `OnSpellStart` in an autotest skips range, chasing and the cast filter (see BUG_LOG).
- **Stock `roshan_spell_block` / `roshan_bash` exist as abilities** (VPK); added to the hero with `AddAbility` + `SwapAbilities` into placeholder slots 4–5.
- **Budget:** the core fix (6 code items) filled a session; the bot simulation and tuning go to the next one.

### 2026-10-31 — mode-1 part 2-fix-2 (inner zone, point dash, border)
- **Find a map area's walls by a walkability scan:** a console command prints a 64-unit grid around the point (`#` = not traversable/blocked, digits = height); the inner side of the walls gives a polygon. Verify with `DebugDrawLine` + a camera on the hero (`PlayerResource:SetCameraTarget`) and one screenshot — matched the bowl on the first try.
- **No `script` console command in tools mode:** add a small Lua `Convars:RegisterCommand` for one-off checks instead.
- **Damage filter by a smaller inner polygon** only while the victim stands in it; outside — normal fight. Test with `ApplyDamage` from a placed unit (deterministic), not with real attacks.
- **Point dash (Skewer-like):** `GetCastRange()` from the balance table, length = min(cursor distance, range), duration = length / speed; stop when the next step leaves the zone — no knockback needed.
- **Zone border in the world:** one ground rope particle (`range_finder_draggable_line`, CP0/CP1) per merged run of cell edges facing walkable outside ground; edges against cliffs/trees skipped → 61 lines. Not visible on a night/fog screenshot — check in daylight.
- **Open:** AI behind the pit wall walks but keeps hitting from outside (`MoveToPosition(target)` does not lead it in); next — route via the pit entrance point.
- **Budget:** pit + fortress rule + point dash + border + autotest filled the session; the bot simulation moves to the next part.

### 2026-10-31 — mode-1 part 2-fix-4 (attack rule, AI entry)
- **Works:** attack vs spell in the damage filter: `entindex_inflictor_const` is nil for auto-attacks. Stock `modifier_disarmed` (AddNewModifier, no ability) blocks auto-attacks of AI heroes; set it every AI tick from state (both in the inner zone → armed), not from order branches.
- **Works:** AI enters an enclosed area via two fixed entrance points (outside → inside); a direct MoveToPosition to the target behind a wall stops at the wall.
- **Fails:** ownerless heroes (CreateUnitByName, no owner) never cast — CastAbility*(-1), ExecuteOrderFromTable, CastAbilityImmediately all dropped. Count a cast by mana/cooldown, not by the order (open bug).
- **Test hygiene:** FindClearSpaceForUnit onto a spot taken by another unit shifts the hero (here: into the inner zone) — move the other unit first. Disarm the player's hero during AI checks or it kills the test unit.
- There is no `script` console command in the Dota client — debug via a temporary `Convars:RegisterCommand`.

### 2026-10-31 — mode-1 part 2-fix-5 (cast false alarm, idle watchdog, safety test)
- **Check WTF first:** `dota_ability_debug 1` hides mana cost and cooldown, so "AI never casts" was a false alarm. Before any AI check run `dota_ability_debug 0`; count casts with `MODIFIER_EVENT_ON_ABILITY_EXECUTED` (`params.unit == parent`).
- **Kill right after RespawnHero is ignored** in the same frame (no entity_killed); in tests wait ≥ 0.5 s between them.
- **FindUnitsInRadius respects fog:** an unseen target → the "no target" branch must also send the AI somewhere sensible; plus an idle watchdog (outside the area, not moving/attacking > 2 s → walk in).
- **Test hygiene:** stray creeps also trigger global counters (blocked hits); count per attacker (`unit.rp_blocked`) in tests.

### 2026-10-31 — mode-1 part 2-fix-6 (start)
- **API checked:** `CDOTA_BaseNPC:GetBaseAttackRange()`, `GetAttackRangeBuffer()`, `GetHullRadius()` exist — use them for a "not in melee reach" check (range + both hulls).
- **Budget:** a new stage in an already long chat hits the 150k hook almost at once — start every stage in a new chat.

### 2026-10-31 — mode-1 part 2-fix-6 (deep wait spot)
- **Worked:** AI wait spot = entrance mouth (middle of the polygon's closing edge) + inward direction × (wait_depth + margin), 5 slots with side/depth offsets, each checked InPit + traversable. Depth measured along the inward direction (distance to the entrance line), not to the mouth point.
- **Failed first:** "arrived" = within 80 of the spot → Hold fired while still walking, the hunter stopped 50 short (depth 260 < 280). Fix: Hold only when stopped within WAIT_NEAR (50) or moving within 30; margin ≥ WAIT_NEAR.
- **Reach check:** `Script_GetAttackRange()` + both `GetHullRadius()`; attack range buffer left out (it only keeps an already started attack). Player rooted at 3 spots along the entrance: min gap 192, no hits.
- **Note:** `sed -i` from Git Bash turns CRLF files into LF — re-save with CRLF after it.

### 2026-10-31 — mode-1 stage R2 part 2b (return bug, simulation, upgrade card)
- **Root cause of the flaky AI return:** after `unit:Hold()` the unit methods `MoveToPosition` / `MoveToTargetToAttack` were silently ignored by ownerless AI heroes (`IsMoving` false, moved 0, no root/stun flags) — `ExecuteOrderFromTable` with the same order worked at once. All AI and bot orders now go through `ExecuteOrderFromTable`. Test: 10 dash carries in different directions/lengths (also over the bowl wall), then the player at the entrance: 10/10 back deep.
- **Debug pattern:** a convar that stops the AI think and issues orders by different methods side by side found the cause in one run; position/pathing dumps (`GridNav:FindPathLength`) ruled out pathing.
- **`ForceKill(false)` fires no `entity_killed`** — tests that need death logic must use `Kill(nil, attacker)`.
- **Bot simulation:** `SendToServerConsole("host_timescale N")` from Lua works; run ends when the pack is dead or by a cap; per-run line + average per pack in the log. The game client crashed once during a pack-2 run at timescale 4 (cause unknown, log overwritten on restart): timescale lowered to 3 and the forced `RespawnHero` between runs replaced by waiting for the normal respawn.
- **Upgrade card:** net table key `card` {open, reason, options} + custom event for the pick works; `Label.html = true` for descriptions; 3 options = one untaken per branch.
- **Charges by script:** spend a spare charge by ending the cooldown a moment after the cast (`SetContextThink` 0.05 s) — the engine starts the cooldown around `OnSpellStart`.
- **Flaky test count = background spawns (2026-10-31):** a "pack spawned = 2" check failed with 3 alive — a random timed spawn landed in the test window. Tests set the mode's own "block timed spawns" flag and count only the units they spawned (tag on the unit).
- **Client crash in long bot series:** the client crashed on the 2nd–4th repeat of the same 3-hero pack in one game at timescale 3 and at 1 (not the timescale). Keep series short (2–3 runs per launch), copy `console.log` before each, cause still open (BUG_LOG).
- **Per-group balance knob:** one global damage % could not fit two packs (one far too easy, one close); a per-pack `damage_pct` kept on the unit and added to the power stack solves it without touching the AI.
- **Tutorial pattern (mode-1):** one script runner (list of waits / calls / wait-for-condition / say-line) with a generation counter, so a skip stops it at once; skip and finish both call one "apply result" function that sets absolute values — then both paths give the same state by construction. Lines go through one `Say(id)` (subtitle now, voice later). Exit blocked by `point_simple_obstruction` + `prop_dynamic` crates; a dash motion controller must also respect the tutorial area or it carries the hero through the blockers.

### 2026-10-31 — mode-1 stage R2 part 2b-3 (tutorial live test, re-sim, close R2)
- **Tutorial bot autotest worked first time** except one check: a skip after the opening line had been heard said it again. Rule: "say once" lines are guarded by the per-run said-counter (`tut_said[id] == 0`), and the test checks the total count is 1 in both skip paths.
- **`console.log` is not reset on a map relaunch** (only on a Dota restart): wait loops must compare the count of a marker line with the count before the command, not just grep for it.
- **Per-pack damage knob confirmed by sim:** pack 2 at +50 % → 0 deaths, at +150 % → 1.0 deaths (2 runs); pack 1 at +150 % → Roshan min HP 24 %. Each upgrade alone (pack 1) lifts min HP to 45–51 %.
- **Crash-safe series:** relaunch the map before every 2 pack-2 runs and copy `console.log` first — no crash this session (2 + 2 pack-2 runs in separate launches).

### 2026-10-31 — mode-1 stage R3 part 1 (crash hunt, boss/shop code, TTS voice)
- **Crash dumps exist and are cheap to read:** Steam writes `D:\steam\dumps\crash_dota2.exe_<time>_1.dmp` (+ `game/bin/win64/*.mdmp`). A 40-line Python minidump reader (exception stream 6 + module list 4) gives the faulting module and offset. All 6 client crashes of 2026-10-31 (owner's long game, bot sims, a 20-min soak) are the same access violation in `server.dll` at one offset (null object, field 0x344) — one bug, server side.
- **Not the cause (measured):** spawning + `Kill` + `UTIL_Remove` of 30 ownerless heroes far from fights (no crash); one hero casting its spells 15× at Roshan (no crash); Lua memory, own particles and thinkers flat over 10 game minutes (minute monitor). Entity count grows only by the stock map's lane creeps/neutrals.
- **Prime suspect:** the last crash came exactly 3 s after Roshan killed a hero that had just hit him = the delayed `UTIL_Remove` of a dead hunter after a real fight. Dead hunters are now kept as dead entities (respawns off); a departing boss is parked (hidden, invulnerable, out of game) instead of removed. Not yet confirmed by a long run.
- **Don't edit Panorama files during a soak:** Tools mode hot-reloads the HUD at once; it muddies the crash timeline.
- **TTS pipeline:** model id from `GET /v1/models` by display name (`eleven_v4`), `POST /v1/text-to-speech/{voice}`, cache by sha256(text|voice|model) next to each master, hand-made masters (no meta file) never regenerated. The local ffmpeg build has no audio filters — decode to s16le with ffmpeg, trim silence (−50 dBFS, keep 0.1 s) and set gain (−18 dBFS RMS, peak ≤ −1.5 dBFS) in Python, write the .wav with `wave`. 21 lines, 1350 characters; compile of the .vsndevts built all 21 .wav.

### 2026-10-31 — mode-1 stage R3 part 2 (boss/shop live, autotest 7)
- **A hero's max HP ignores `SetBaseMaxHealth`:** a stock hero used as a boss came out with 1242 HP instead of 5000 — the engine recalculates hero max HP from stats. Fix: the boss AI modifier returns `MODIFIER_PROPERTY_HEALTH_BONUS` = target − natural max (measured after `CalculateStatBonus(true)` with the bonus at 0).
- **Attack orders on a target in the fog are refused** ("invalid order … Target can't be seen by the unit's team"), every think — a boss spawned outside the pit never fought. AI: if `not CanEntityBeSeenByMyTeam(target)` → move to the target's position instead.
- **`unit:MoveToPosition` right after `CreateUnitByName` is ignored for ownerless units too** (same as after `Hold`, R2 2b): a trader stood at its spawn. Use `ExecuteOrderFromTable` a tick (0.1 s) after the spawn; spawn walkers at a reachable point (pit mouth), not behind a wall.
- **Lines said with `subtitle = false` are not in the line table:** a voice test that counts table entries saw 15 of 21 lines; list the plate-only ids explicitly.
- **Sequential test runner:** a list of `{fn}` / `{wait = s}` / `{till = fn, max = s}` steps on one context think keeps a 25-check scenario flat (no nested callbacks).
- **A Lua error inside a context think silently ends that think:** two soak runs lost their bot (and the end marker) — once on a sim-only counter (`self.sim` nil outside a sim run), once on `IsValidEntity(true)` (a "reserved while precaching" flag in the unit field → "Parameter type mismatch"). Shared bot code guards run-specific state; a field that can hold a placeholder is checked with `type(x) == "table"` first. Watch soaks with a monitor on `Script Runtime Error` and stop at once.
- **Crash hunt result:** with dead hunters kept (not removed) two 20-game-minute soaks (×2, packs 1–2 + noise + boss at 8:30, 14 heroes) ran without a client crash; before, a soak crashed at ~10 min. Supports the delayed-hero-removal suspect, not proof.

### 2026-10-31 — mode-1 stage R4 (Roshan's voice, stage-3 fixes)
- **Hand-made voice masters import through the same pipeline** (`voice_pipeline.py`): an `.mp3` without a `.json` next to it is treated as hand-made and never regenerated; the wav is trimmed/levelled and one `.vsndevts` per speaker is written (`roshan.vo.<id>`, `compile_addon_resource` builds events and wavs). Texts of hand-made masters are not stored anywhere — subtitles for them need the text from the owner (the API key had no `speech_to_text` permission: HTTP 401 `missing_permissions`).
- **TTS tags vs masked swearing:** `[dry]`/`[shouts]` (Latin) are eleven_v4 audio tags and must stay in the text; `[..]` around Cyrillic is a swearing mask and is read in full. One regexp for both broke the first attempt (the replacement string `\1` lost its backslash when pasted through a heredoc — use `lambda m: m.group(1)`).
- **One speech queue for everyone:** `Say` computes the delay from the *other* speaker's and its own `talk_until`; reactive hook lines are skipped (not queued) while anyone talks, story lines (`force`) queue. Per-line cooldown 25 s. Lines without a RU text are voice-only (`M.NO_SUBTITLE`) so the HUD never shows a raw token.
- **A flee needs a hard deadline outside the stun check:** the Ursa AI returned early while stunned/carried, so the "flee over" check never ran; the deadline now sits first in the think, the target is a far walkable point (`FindWalkPoint(2200)`), time 35 s.
- **Hero template leftovers:** model replaced on the client with `MODIFIER_PROPERTY_MODEL_CHANGE`; template wearables are hidden with `EF_NODRAW` on `dota_item_wearable` children (none were found on the hero at runtime — the visible Tidehunter parts came from the model swap itself); template voice silenced with `"VoiceFile" ""` in the hero KV (the log then shows `Failed to start voice … tide_lasthit` instead of playing it).
- **Screenshots go stale when the Dota window is not in front:** three identical files (same md5, same game clock). `ShowWindow(h, 9)` + `SetForegroundWindow` right before the shot fixes it.

### 2026-10-31 — mode-1 stage R5 (subtitles + icons)
- **Subtitles:** the HUD looks up `#roshan_line_<id>` and hides the box when the token is missing, so "no subtitle" = no localization key. Source text: strip `[english tag]` (bracket not glued to a letter), in-word `[..]` → one `*` per letter. Check by comparing every `"roshan"` id of the LINES table against the localization file (server Lua cannot read it).
- **Icons:** source art is 1024² JPG → center-crop to 11:8, resize 88×64 PNG into `content/<addon>/panorama/images/items/<name>.png`; `validate_and_sync_precache` compiles them. Its `icon_compile_errors` can be a false alarm (log says "OK: 8 compiled, 0 failed, 2 skipped"): verify `*_png.vtex_c` exist.
- **Shell:** Cyrillic file names in a bash heredoc python get mangled; match by the timestamp suffix instead.
- **Demo helpers:** `roshan_cardpick [id]` picks a mutation without a click, `roshan_claw` gives the Claw (card otherwise covers the screen).

### 2026-10-31 — mode-1 stage R6 (voice channel + consumables)
- **Sound sliders (console):** `volume` = Master, `snd_gamevolume` = Game, `snd_musicvolume` = Music, `snd_voipvolume` = voice chat, **`snd_gamevoicevolume` = "Game v.o. volume" = unit speech**. Found with `find volume` in the console.
- **Hero speech is not a mixgroup:** stock hero/announcer VO events (`game_sounds_vo_*.vsndevts_c`, decompiled with `Source2Viewer-CLI -i <file> -b DATA`) carry `type = "dota_update_vo_switch"` and no `mixgroup`; the type itself routes them to the unit-speech channel. Our `*.vo.*` events were `dota_src1_2d` (Game channel) -> switched to `dota_update_vo_switch`. `GetSoundDuration` stays > 0 and the lines play. The channel itself is engine-internal: no console command shows it, so it needs an ear check (Game 20 %, Unit speech 100 %).
- **Consumable pattern:** `item_lua` with `ItemRequiresCharges` + `ItemInitialCharges`; spend with `SetCurrentCharges`, `RemoveItem` at 0. Item icon `AbilityTextureName "item_rp_x"` resolves to `images/items/rp_x`. Modifier model scale: `MODIFIER_PROPERTY_MODEL_SCALE` returns percent.
- **Test traps:** a 30 s buff from the previous run hides the effect in a rerun - clear it first; right after the use order wait ~1.5 s before reading scale. Dota not in foreground = stale screenshots (see stage 11) - bring it forward with `SetForegroundWindow`.
- **Boss resize guard:** `FindModifierByName` on a dead boss returns nil -> check before use.

## mode-1 stage 4c (voice back on the Game channel, louder)
- **`dota_update_vo_switch` is not usable for custom voice:** the 4b switch made all our voice silent although `GetSoundDuration` was > 0. Keep `dota_src1_2d`. `GetSoundDuration` proves compilation only, not audibility.
- **Loudness:** gain to -13 dBFS RMS, then a tanh soft limiter above a 0.55 knee, peak <= -1 dBFS (pure Python, ffmpeg only decodes).
- **Ducking from an addon:** `scripts/soundmixers.txt` (base game, read with `Source2Viewer-CLI --vpk_filepath`) matches sound groups by `path_substring` of the sound path. Group `Video` (`video_ducks_music`, mix vol 1.0) has `causes_ducking = 1`, group `All` is ducked to 80 % (about -2 dB, not tunable). Group `Stingers` also ducks but its mix vol is 0.5, so it would make the voice quieter. Our wavs now live in `sounds/vo/<speaker>/video_ducks_music/`. Whether it is audible is an ear check.
- **Own volume:** `EmitSoundOnClient` has no volume; for a percent other than 100 the hero plays the event with `EmitSoundParams(ev, 0, pct/100, 0)`. Console: `roshan_vo_volume 0..200`. Values above 1.0 in the event file itself were not tried.

## mode-1 stage 6b (hunter voices, shared queue)
- **Voice per hero from a table:** the TTS pipeline reads hero voice ids from a local markdown table (ids are not secrets, the API key stays in the env file); one speaker per hero, events `hunter.vo.<hero>.<line>`, one `.vsndevts` per speaker, masters cached by text+voice+model hash.
- **One queue for all speakers:** `Say` delays a new line behind the latest line of anybody (`talk_until.any`), so Roshan, the Courier and hunters never overlap. Hunter story beats (spawn, death, boss phases) queue at most 6 s; reactive ones (hit, hurt) are dropped when somebody talks and have a per-speaker gap of 17 s. Roshan's own lines are never dropped.
- **Sim needs the chapter running:** `roshan_sim` before the tutorial ends fails with `packs_sent` nil; skip the tutorial first (`roshan_tutorial_skip` works only after the hero exists).

## mode-1 stage 7 session 1 (R9: voice loudness, voice queue)
- **Measure, don't guess:** `soundcard` (pip) records the Windows output as loopback; send console commands over netcon 2121 from the same script and print peak / loudest-1 s RMS per window. A fight measured -21..-25 dB, our voice at volume 1.0 about -26 dB (lost in the mix).
- **Event volume above 1.0 works:** `EmitSoundParams(ev, 0, vol, 0)` with vol 3 / 4 / 6 gave about +5 / +8 / +11 dB; `volume = 4.0` in the `.vsndevts` gave about +10 dB too. Playing the same event twice on one entity adds nothing. Voice now x4 in code (`VO_GAIN`), times `roshan_vo_volume`: 7-10 dB over a fight.
- **Denser wavs:** compressor (30 ms RMS window, 4:1 above -24 dB of the line RMS) + makeup to about -10 LUFS + the old soft limiter; `voice_pipeline.py --reimport` rebuilds wavs/events from masters without API calls. The old ffmpeg build has `ebur128` (no `peak=` option) for LUFS checks. A running Dota seems to keep the old wav data across map reloads; the louder files count after a client restart.
- **Fade on stop:** stock events use `volume_fade_out = <s>`; ours have 0.2, so `StopSoundOn` fades the cut line out.
- **Voice queue:** one current line + a waiting list in `M:Say`; priority death 5 > kill 4 > Roshan 3 > Courier 2 > chatter 1 (the victim's death line beats the killer's gloat that fires first in the same frame); higher cuts lower, others wait 2 s; the scripted tutorial only queues (no cut, no expiry); a dead speaker's lines are dropped. Reset the queue on tutorial skip/restart, or a leftover line holds back the first tutorial line.
- **Test traps:** `ForceKill(false)` did not reach our `entity_killed` handler; `Kill(nil, attacker)` does. Panorama of a background Dota window stalls: the SPACE-hold skip fired minutes later -> bring Dota to the foreground before autotest 6. `RestartTutorial` removes live hunters: running it during a fight crashed the client (same family as the hunter-removal crash) - run autotest 6 on a fresh map.


### 2026-11-01 — mode-1 stage R10, part 1 (chapter 1 by goals)
- **Goals chain** (`roshan_goals.lua`): each goal = Goal<n> (enter) + GoalCheck<n> (polled 0.25 s) + optional GoalAfter<n>; net table key "goal" drives the HUD panel; a generation counter stops a stale check. Timers removed (packs, Ursa, shadow line), noise heroes and power per minute kept.
- **Border by crates:** zone edges farther than `goals.pit_edge` (700) from the pit center get a stock crate prop + two `point_simple_obstruction` (48 apart); knockback only outside that radius -> no sticking at the pit walls. Autotest: no push at 480-680 from the center, push past the crates.
- **Cutscene stub:** net table "cut" (caption tokens, duration) -> full-screen colored panel, per-frame `preTransformScale2d` zoom + short shake, `HUDElements` hidden; stock `modifier_invulnerable` + `modifier_stunned` on the hero; the existing SPACE-hold event ends a cutscene first, else skips the tutorial.
- **New localization tokens are not picked up by a map relaunch** ("failed to localize"): restart Dota before looking at new texts.
- **Voice queue vs story lines:** low-priority goal lines with a short wait get dropped behind reactive Roshan / death lines; give them a long wait or chain them (`SayChain`: next line only when the queue is idle).
- **Autotest 12** (bot with cheats, ~90 s): goal order 1-8, panel, crates up/down, pit edge free, river push, 4 cutscenes + a skip, fork, summary PASS; Courier goal lines FAIL (5 dropped) -> waits raised to 15 s, not re-run.

### 2026-11-01 — mode-1, stage R11 (clean screen)
- **Stock HUD off:** JS `GameUI.SetDefaultUIEnabled(DotaDefaultUIElement_t.X, false)` for TOP_TIMEOFDAY, TOP_HEROES, FLYOUT_SCOREBOARD, ACTION_MINIMAP, INVENTORY_SHOP/QUICKBUY/COURIER/GOLD, SHOP_*, TOP_BAR*, QUICK_STATS, AGHANIMS_STATUS (names from `verify_vscript_api "DOTA_DEFAULT_UI_"`; guard `!== undefined`). Abilities, HP/mana, items and the top-left menu stay (screenshot checked).
- **No gold at all:** `GameMode:SetModifyGoldFilter(function() return false end)` — a creep kill leaves gold unchanged (starting 600 stays, hidden).
- **Floating "+N" over a dying creep:** Lua sends the death position (`Send_ServerToAllClients`), not the entindex (the unit is gone soon); JS projects it every frame with `Game.WorldToScreenX/Y` × `1080 / Game.GetScreenHeight()` — same size at any camera zoom.
- **Own toggle key:** `Game.AddCommand(randomName, fn)` + `Game.CreateCustomKeyBind("B", randomName)` toggles our Courier tray; server says "available" (Roshan near the Courier), the client keeps "shown" (opens once on arrival, then X / B / button).
- **Glyphs:** "✕" renders as an empty box in the default Panorama font — use a plain "X".
- **VScript Lua has no file io, no `script` console command:** route points (`roshan_mark`) are printed as `[ROSHAN_MARK] {json}` and synced from console.log by a Python script into JSON + a generated `roshan_points_data.lua` (loaded with `pcall(require)`). Camera yaw/distance live on the client: `GameUI.GetCameraYaw()`, distance = |`GetCameraPosition` − `GetCameraLookAtPosition`|; restore with `SetCameraTargetPosition`, `SetCameraYaw`, `SetCameraDistance` (all in `cl_panorama_script_help_2`).
- **`GameRules:SendCustomMessage` text is passed through localization** ("failed to localize" in the log for plain text) — whether it still shows in chat is unchecked.
- **Roshan voice rules:** shared reactive cooldown 25-30 s (kill / respawn lines exempt), a Roshan reactive line is dropped while Roshan speaks or waits in the queue (no Roshan->Roshan cut, even by a higher-priority kill line), hook lists are decks, never the same line twice in a row. Autotest 13: 5 game minutes of random hooks + Courier + hunter chatter — 13 Roshan lines, 0 cuts, 0 repeats, 0 short gaps. `host_timescale` from Lua barely sped the run up (≈1.3×) while Dota was unfocused.
- **`SetContextThink` with a fixed name inside its own callback:** if the callback (re)registers a think with the same name and then returns `nil`, the engine removes the NEW think — a chained step timer silently stops (cutscene hung, no error). Use `DoUniqueString(name)` for chained one-shot timers.
- **Panorama camera:** yaw / pitch / distance are settable (`GameUI.SetCameraYaw`, `SetCameraPitchMin/Max`, `SetCameraDistance`); no FOV API, no cursor-hide API. A Lua camera = `CreateModifierThinker` + `PlayerResource:SetCameraTarget`.
- **New localization strings need a full Dota restart** (map relaunch is not enough): "failed to localize" until then.
- **Autotests vs auto-played intro scenes:** a test must end any scene already playing (the map's cold open) first, or it inherits a locked hero; a previous test run's timers keep running after `script_reload` and pollute the next run — restart the map before a re-run.
- **New sound events need a full Dota restart too:** a `.vsndevts_c` compiled while Dota runs is not loaded by a map relaunch — `GetSoundDuration` returns 0 and the line is silent (autotest counted 12/30 voiced; after a restart 29/30). Restart Dota via `quit` + `steam.exe -applaunch 570 -addon <addon> -tools` (Steam adds the user's launch options), wait for NetCon, then launch the map (a command sent before the menu is up is lost).
- **Scripted scene lines must bypass the voice queue:** a scene step that waits "voice length + gap" breaks when its line is queued behind the previous one (the length read is stale, the next line comes early and waits >2 s → dropped). Film lines now always play at once (`opt.film`).
- **Hide own Panorama panels by a root class + CSS, not `.visible`:** later updates (goal box) bring panels back; `.FilmCinema #Goals { visibility: collapse; }` on the context panel holds for the whole scene.
- **`AddNewModifier` on a dead hero returns nil:** a scene started while Roshan waits to respawn crashed on `:SetStackCount`; respawn first (`RespawnHero(false, false)`).
- **Crossing tests need a free straight path:** pick the crate where `GridNav:FindPathLength(start, end)` is short with the blockers off; a cliff behind the first crate made "mark mode passes crates" fail.

### 2026-11-01 — mode-1, stage R13 (cinema rework)
- **Screenshots of a frozen frame:** with `-tools` the process main window is the Asset Browser; the game window ("Dota 2") is a separate top-level window. When it is behind other windows `jpeg_screenshot` returns the same stale frame (identical md5) — the scene looked "not shown". Bring the "Dota 2" window forward (EnumWindows by title + `SetForegroundWindow`) before every shot.
- **Living models in a scene:** do not stun or set animation rate 0 — "on hold" = ROOTED + DISARMED + SILENCED + MUTED + invulnerable + no health bar; idle animations go on. A gesture per line (`StartGesture`, Roshan model: ATTACK, CAST_ABILITY_1..3, CAPTURE, FLAIL). A `prop_dynamic` does not animate: the Courier is a real unit with `MODIFIER_PROPERTY_OVERRIDE_ANIMATION` = ACT_DOTA_RUN (flight loop) + `MODIFIER_PROPERTY_VISUAL_Z_DELTA` sine (bob, computed on both sides from game time).
- **Camera yaw rule (measured):** the camera sits at look-at + (sin yaw, −cos yaw) · horizontal distance. A clear view = sample the line camera → chest: above `GetGroundHeight` + 40, no `GridNav:IsNearbyTree` below 380 height, `TraceLine` not hit; otherwise turn the yaw 10° steps both ways. Scenes on the open river, pitch 50–65, dist 700–1100, 6–15 s eased moves, one cut.
- **Comic panels:** owner JPGs → 1920×1080 PNG in `panorama/images/custom_game/...`, compiled by the layout compile; per-frame `preTransformScale2d` ≥ 1.1 so the drift + shake never shows the edge.
- **Test timing vs voice length:** a test that answers a choice after a fixed delay broke when the line before it got longer (5 s); use a short line.

### 2026-11-01 — mode-1, stage R14 part 1 (prologue timing, tutorial on the river, route fence; code only)
- **ElevenLabs key scopes:** a restricted API key may lack `speech_to_text` / `user_read` (HTTP 401 `missing_permissions`); TTS still works. Without STT, word timing came from the processed wav itself: 50 ms RMS frames, runs below -40 dBFS ≥ 0.2 s = sentence pauses (prolog_5: one pause 4.45-4.65 s = before «Готовьтесь»).
- **Loopback recording is all zeros when Dota stops presenting frames** (`Present was waiting ... without a present event`, screenshots fail): the engine produced no audio at all although `roshan_emit` ran; a Windows beep recorded fine at -9 dB. Restart Dota before any sound measurement.
- **Film steps timed to words:** line step `after = s` (next steps run over the voice) and `gap = s` (instead of the 0.4 s default) — panels change without pauses, shutters/hits play over the voice.
- **Route fence:** play area = pit + capsules (width 1200) along the owner's points in order; crates + two obstructions on every grid edge (96) between the area and walkable ground outside; a scene done -> the area grows, edges no longer on the border blow apart (techies detonate fx on every 3rd), new edges get crates. Not live-tested yet.

### 2026-11-01 — mode-1 stage R14 part 2 (live check of the prologue)
- **Two Dota windows in tools mode:** `MainWindowHandle` of `dota2.exe` can be the *Asset Browser*, not the game. Focusing it leaves the game window in the background: no new frames (screenshots repeat one frame) and **no audio at all** (Windows session peak ~1e-9, even with `snd_mute_losefocus false`). Find the game window by title `Dota 2` (`FindWindow`). From an agent shell `SetForegroundWindow` (also with Alt tap + `AttachThreadInput`) was refused by Windows — asking the owner to click the game window once worked.
- **Loopback audio check:** `soundcard` loopback on the default speaker + netcon in one script (`.private/tools/rec_prolog.py`); a correlation with the source wavs finds each voice line's real start (prolog_1..5 at 1.1/8.1/16.2/20.7/31.3 s). Subtracting the voice leaves -30 dB residue, so short effects under a voice cannot be proven; low-band (<150 Hz) jumps of +13..+21 dB at the slam times and +8..+10 dB at the roar are evidence, the shutter click was not isolated. For a clean proof, play effects with the tutorial silent.
- **`script <lua>` is not a console command here** ("Unknown command"), and `snd_playsounds` neither — use the addon's own `roshan_emit <event>`.

### 2026-11-01 — mode-1 stage R14 part 3 (autotest 6 / route fence)
- **Fence from GridNav + own obstructions:** rebuilding the fence re-read `GridNav:IsBlocked`, and our own `point_simple_obstruction`s made the outside cells "blocked", so every edge vanished (−33 crates). Fix: cache walkable cells per map before any obstruction exists (`route_walk`), clear the fence in `InitRoute`.
- **Props in the pit are in fog from the river:** a bot `CAST_TARGET` on them fails with "invalid order (26). Target can't be seen". Fix: `AddFOWViewer` at the tutorial spot (removed in `TutClear`), training points skip the pit, spawn spread kept inside the fence.
- **Game window focus:** the game (tools mode) barely advances while another window is in front; a background PowerShell loop `WScript.Shell.AppActivate("Dota 2")` every 2–3 s keeps it running during long autotests.
- **Route tests must move the hero physically** before and after each opening: `InPlayArea` checks passed while the river spot was open toward the road (new `river_holds` check FAILs).
- **After `script_reload`, relaunch the map** for fence tests: `InitRoute` is not re-run, a cache built with the fence standing is wrong.

### 2026-11-01 — mode-1 stage R14 part 4 (route fence closed, autotests 6/15 PASS)
- **Old distance filters vs a new zone shape:** the route fence kept the old "no crates within pit_edge of the pit center" rule; the river circle's road side lies ~290 from the center, so that side had no crates. Dropping the filter for the route closed it (42 crates); crates near the pit only appear on walkable ground outside the area.
- **Autotests and running films:** `film_auto = false` stops new scenes only; a scene already playing mutes tutorial lines. End it (`EndScene(true)`) before restarting the tutorial.
- **netcon output arrives late** (tens of seconds) during long runs; for timed screenshots use a fixed wait from the command (`wait_response_ms`) with the focus loop running, not the log lines. `dota_camera_lock 1` keeps the camera on Roshan.

### 2026-11-01 — mode-1 stage R14 session 2 (music plan check, blocked)
- **Scoped ElevenLabs keys:** a key without `user_read` gets 401 `missing_permissions` on `/v1/user` and `/v1/user/subscription`, so the plan tier cannot be read from the API; `/v1/models` still works. Ask the owner for the plan name or a key with `user_read`.
- **Eleven Music terms (music-terms, 09.10.2026):** Music API — paid plans only (Free: no API, no downloads); Free/Starter — "Music Streaming Distribution" prohibited, Creator+ permitted; all non-Enterprise plans exclude film/TV/radio and "Studio Games"; Free–Pro "individual use only". YouTube is not named — confirm before use. Cost ~900 credits/min, 3 s–5 min per track.

### 2026-11-01 — mode-1 stage R14 session 2b (music)
- **Eleven Music API:** `POST /v1/music`, `model_id = "music_v2_5"` (underscore). Plain tracks: `prompt` + `music_length_ms` + `force_instrumental`. Timed tracks (a comic with fixed beats): `composition_plan.chunks` with `duration_ms` (3–120 s each), `text` (`[Section] {direction}`), `positive_styles` / `negative_styles` (`force_instrumental` is prompt-only, so vocals go to `negative_styles`). Five tracks (~5 min) in one go, each answered in under a minute.
- **Music group trap:** a sound path containing `music/` lands in the engine Music group, which follows `snd_musicvolume` — the owner's was 0, so the music was silent. Keep custom music on a neutral path (`sounds/roshan_bgm/`), own volume via a script percent.
- **mp3 straight into vsnd:** `.mp3` sources compile directly (compile the `.vsndevts`); a 60 s stereo 160 kbps track ~1.2 MB.
- **Loops without loop points:** file = period + 2 s, sine fade-in head and fade-out tail; two events of the same file (`.a`/`.b`) restarted every period from a think — the copies crossfade, jitter of a tick is masked.
- **Ducking from Lua:** `EmitSoundParams(ev, 0, vol, 0)` on an already playing event is documented as "plays/modifies"; the script changes volume when a voice line starts/ends (log shows it). Audible effect not yet confirmed: the loopback test failed because netcon commands arrived late while a scene was still running — run such tests with no scene and check the log order first.
- **Volume above 1.0 (mode-1, 8b-3):** a script volume of 2.0 via `EmitSoundParams` sounded the same as 1.0 (owner by ear) — treat 1.0 as the top; a "0-200 %" command is a lie, cap it at 100 %.
- **Ducking depth:** −9 dB of script ducking under voice lines was "almost inaudible" to the owner on headphones (the voice wavs also sit in a `video_ducks_music` path); ×0.6 (−4.4 dB) is the new default.
- **Quest NPC as a hero unit:** `CreateUnitByName("npc_dota_hero_pudge", …, DOTA_TEAM_BADGUYS)` + `modifier_invulnerable` = untargetable, uncontrolled actor; `PrecacheUnitByNameSync` in `Precache` loads its model, hook particle and sounds. Scene actors are removed at scene end — a unit that must outlive the scene is lent to `st.actors` in `setup` and taken back in `cleanup` (cleanup runs before the actor removal).
- **Fake meat hook:** `pudge_meathook.vpcf` with CP0 = `attach_weapon_chain_rt` on the caster, CP1 = tip, CP2 = (speed, range, width), CP3 = (time); move CP1 back to the caster for the retract. Pull a unit with `SetAbsOrigin` lerp; pull a hero with `modifier_knockback` whose center is placed behind the hero (knockback pushes away from the center).
- **Timed race needs a refill:** a fixed camp of 9 creeps was eaten in ~20 s of a 60 s race; spawn more when fewer than 4 are left.
- **`script_reload` drops voice lengths:** after a reload scene lines log without "(voice N s)" and cut each other (fallback seconds); judge scene timing only on a fresh `dota_launch_custom_game`.

## mode-1, stage 9-1 (road talk, quest 2, Ursa transmission) — 2026-11-01
- **Works:** transmission scenes (`mode = "tx"`) reuse the scene engine for on-the-move talk: bottom bar + portrait, the game goes on; a cinema scene started later just ends them. New speakers need three things: voice prefix in the `VOICE` table, a portrait unit in the HUD `PORTRAIT` map, `roshan_who_<speaker>` string.
- **Works:** an NPC on a tree top = a normal hero unit + a Lua modifier with `MODIFIER_PROPERTY_VISUAL_Z_DELTA` (stack count = height); hop arcs change the stack every 0.05 s, the unit itself stays on the ground.
- **Failed → fixed:** the camera visibility check called every shot "blocked" when the NPC sits inside a tree (the trace ends in the tree crown). Fix: aim at the drawn height (origin + perch) and skip the last samples next to the unit.
- **Failed (open):** `take_game_screenshot` returned the same stale frame twice in a row (different file names, identical 202 KB image, old HUD numbers) after the window was activated by script. Do not trust a screenshot whose HUD numbers do not match the log.
- **Noise:** each Monkey King hero unit prints "Creating monkey at <t>" once per second to the console (engine, not our code); clones are removed at the end of each round.
