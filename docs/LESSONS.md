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
