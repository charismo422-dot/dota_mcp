# `dota_mcp` — Agent Rules & Engineering Protocol

This document is the single source of truth for AI coding agents (Antigravity, Claude Code, and others) working in the `dota_mcp` repository or using the `dota2-workshop-mcp` server to build Dota 2 Custom Games.

---

## 1. First-Time Setup & Environment Verification

Before creating or modifying any Dota 2 custom game on a Windows machine:
1. If `.venv/` or `bin/Source2Viewer-CLI.exe` is not yet installed, run the idempotent setup script from the repository root:
   ```powershell
   python setup.py
   ```
   *(or `.\setup.ps1` in PowerShell).*
2. Verify the MCP server and local Dota 2 Workshop Tools installation by calling the MCP tool **`run_mcp_self_test`** (or `.\.venv\Scripts\python.exe -m src.dota2_mcp.diagnostics --bootstrap`).
3. Ensure Dota 2 Workshop Tools is launched without Administrator privileges (`RUNASADMIN` must not be set on `dota2.exe` or the agent IDE) and with Steam launch options:
   ```text
   -netconport 2121 -console -condebug
   ```

---

## 2. Project Documentation Map

Always consult and follow the project's technical documentation:
- **Full Technical Specification:** [docs/TECHNICAL_SPEC.md](./docs/TECHNICAL_SPEC.md)
- **Agent Engineering Self-Check Protocol:** [docs/SELF_CHECK_PROTOCOL.md](./docs/SELF_CHECK_PROTOCOL.md)
- **Bug & Fix Log:** [docs/BUG_LOG.md](./docs/BUG_LOG.md)
- **Lessons Learned (agent self-learning):** [docs/LESSONS.md](./docs/LESSONS.md)
- **Idea Bank (MCP features):** [docs/IDEAS.md](./docs/IDEAS.md)
- **Staged Live Test Plan:** [docs/TEST_PLAN.md](./docs/TEST_PLAN.md)
- **Custom Game Development Workflow Skill:** [.agents/skills/dota2-custom-game-dev/SKILL.md](./.agents/skills/dota2-custom-game-dev/SKILL.md)
- **Dota 2 7.41+ Reference:** [.agents/skills/dota2-custom-game-dev/references/DOTA2_741_REFERENCE.md](./.agents/skills/dota2-custom-game-dev/references/DOTA2_741_REFERENCE.md)
- **Working Addon Example (`mcp_test`):** [examples/mcp_test/README.md](./examples/mcp_test/README.md)

---

## 3. Mandatory Technical Invariants

1. **Zero Hallucinated Dota 2 Assets or APIs:**
   - **NEVER** guess or invent paths to models (`.vmdl`), particles (`.vpcf`), sound files (`.vsndevts`), sound event names, animations (`ACT_DOTA_*`), attachment points (`attach_*`), or particle `Control Points`.
   - **ALWAYS** retrieve real asset paths and parameters via MCP tools:
     - `search_dota_assets` — find `.vmdl`, `.vpcf`, `.vsndevts`, `.vmat`, `.vtex` in `pak01_dir.vpk`.
     - `search_sound_events` — find exact sound event names (e.g. `Hero_Huskar.Inner_Fire.Cast`) inside `.vsndevts_c`.
     - `get_base_dota_definition` — inspect real Dota 2 (7.41+) hero, ability, unit, or item KeyValues definitions.
     - `inspect_model` — verify valid `ACT_DOTA_*` activities and `attach_*` points on a `.vmdl`.
     - `inspect_particle` — inspect `Control Points` (`CP0`..`CPn`), child particles, initializers, and operators of a `.vpcf`.
     - `verify_vscript_api` — verify real Lua VScript functions, classes, and enum constants against the running Dota 2 engine via `script_help2`.

2. **Safe Map (`.vmap`) Manipulation:**
   - **NEVER** read raw `.vmap` files directly into the LLM context window (they can contain megabytes of mesh data).
   - **ALWAYS** use the dedicated MCP map tools: `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, `remove_map_entity`, and `compile_addon_resource`.

3. **KeyValues Validation, Precache & Localization:**
   - Place executable scripts and KV files in `game/dota_addons/<addon>/` and source assets (`.vmap`, Panorama `.xml`/`.css`/`.js`, `.png` icons) in `content/dota_addons/<addon>/`. Never use the obsolete Source 1 `resource/flash3` folder.
   - Always add localization strings via `upsert_localization` (`UTF-16` encoding by default).
   - Always run `validate_and_sync_precache` before launching or reloading a custom game to validate KV syntax, verify asset existence in `pak01_dir.vpk`, and auto-generate `auto_precache.lua`.

4. **Self-Check, Live Verification & Bug Logging:**
   - Before generating KV or Lua code, verify against [docs/SELF_CHECK_PROTOCOL.md](./docs/SELF_CHECK_PROTOCOL.md).
   - Test changes live in Dota 2 using `run_console_command` (`dota_launch_custom_game <addon> <map>` or `script_reload`) and check `read_latest_console_log` to confirm zero Lua runtime errors. For anything visual (HUD, Panorama, cutscenes, effects) take `take_game_screenshot` and look at the image (≤ 3 per stage, see §4).
   - Record any discovered MCP or custom game bug into [docs/BUG_LOG.md](./docs/BUG_LOG.md) via `log_bug_report`.
   - Keep [docs/TECHNICAL_SPEC.md](./docs/TECHNICAL_SPEC.md) synchronized whenever tool signatures or architecture in `src/dota2_mcp/` change.

5. **Working Memory Protocol:**
   - **Before a task:** grep the relevant sections of [docs/LESSONS.md](./docs/LESSONS.md) and, if present, the owner's local files (`.agents/rules/owner-*.md`, `.private/STATUS.md`).
   - **After a task:** append new findings (what worked, what failed, how it was fixed) to `docs/LESSONS.md`; update `.private/STATUS.md` if it exists.
   - **Ideas:** record MCP feature ideas in [docs/IDEAS.md](./docs/IDEAS.md); record custom-game ideas in `.private/IDEAS_GAMES.md` (local only, never commit).
   - `.private/`, `CLAUDE.local.md` and `.agents/rules/owner-*.md` are gitignored personal files; never commit or publish them.

---

## 4. Бюджет сессии (обязательно)

1. **Одна сессия = один этап.** Старт: `/stage`. Конец: `/wrap` (последним в отчёте — готовое «Сообщение для новой сессии» `/stage …`, с какого места продолжать). Потом СТОП — без вопросов и без предложений новых задач. Следующий шаг берётся только из плана (`docs/TEST_PLAN.md` / `STATUS.md`), не придумывается.
2. **Минимум:** делать только то, что проверяет пункт плана. Варианты, улучшения, «умнее», доп. настройки — одной строкой в `docs/IDEAS.md`, не делать.
3. **`mcp_lab` — песочница:** не полировать вёрстку и вид.
4. **Автотест:** PASS один раз; повтор только после правки кода.
5. **Скриншоты:** не больше 3 за этап; перед снимком вывести окно Доты на передний план.
6. **Язык игры** до релиза только русский; EN-строки не писать, пропуски EN игнорировать.
7. **Логи, LESSONS, большие файлы** — только `grep`/`tail`/диапазоны строк. Из LESSONS читать только нужные разделы.
8. **3 неудачные попытки на одной ошибке** — стоп, запись в `STATUS.md` и `docs/BUG_LOG.md`.
9. **Контекст:** при предупреждении хука (> 150k) — закончить текущий пункт и сделать `/wrap`. Новых пунктов не начинать.
10. **Владелец не пишет в законченную сессию;** результат его проверки приходит первой строкой новой сессии (`/stage <результат>`).
