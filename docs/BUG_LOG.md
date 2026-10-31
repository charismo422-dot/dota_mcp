# Журнал багов, ошибок и исправлений (`BUG_LOG.md`)

В этот документ автоматически (через инструмент MCP `log_bug_report` или напрямую агентом) записываются все обнаруженные баги, ошибки инструментов MCP, проблемы компиляции `.vmap` / Panorama и ошибки времени выполнения Lua/KV во время тестовых запусков на Windows.

Агент обязан проверять этот файл перед началом работы и пополнять его при каждом исправленном инциденте.

---

## Зафиксированные инциденты и правила обхода

### [INIT-001] Защита от различий версий формата `keyvalues2` в `.vmap`
- **Дата:** 2026-10-21
- **Компонент:** `vmap_builder.py` (Работа с `.vmap`)
- **Потенциальная проблема:** В разных обновлениях Source 2 блок свойств сущности `CMapEntity` внутри текстового `.vmap` может использовать разные типы контейнеров (`EditGameClassProps` или `entity_properties`, а также разные версии заголовка `<!-- dmx encoding keyvalues2 4 format vmap ... -->`).
- **Решение (заложено в код):** Вместо жестко закодированного шаблона `CMapEntity`, модуль `vmap_builder.py` при добавлении новой сущности находит существующий узел `CMapEntity` прямо внутри сконвертированного пользователем `template_map.vmap`, клонирует его точную структуру, заменяет `id` (UUID), `origin`, `angles`, `scales` и ключи внутри блока свойств. Это гарантирует 100% совместимость с любой версией Dota 2 Workshop Tools.

---
<!-- Новые записи добавляются ниже автоматически -->

### [2026-10-22 13:13:00] Компонент: `vmap_builder.py` (🔴 1 & 🔴 2: Архитектура `CMapEntity`, ссылки `children` / `CVisibilityMgr` и уникальность UUID/`nodeID` в `format vmap 40`)
- **Симптом / Ошибка:**
  1. В реальном сконвертированном `template_map.vmap` (`format vmap 40`, см. `docs/reference_samples/template_map_vmap_sample.txt`) блоки `"CMapEntity" { ... }` располагаются на верхнем уровне файла и разделяются пустой строкой (`\n\n`) без запятых, тогда как ссылки на них `"element" "<uuid>"` хранятся через запятую в массивах `"children" "element_array"` (внутри `"CMapGroup"` / `"CMapWorld"`) и в `"visbility" "CVisibilityMgr"` (`"nodes" "element_array"` параллельно с `"hiddenFlags" "int_array"`).
  2. Старая реализация `add_map_entity` заменяла только верхний `"id" "elementid"` (`count=1`), оставляя дубликаты UUID у вложенного `"relayPlugData" "DmePlugList"`, не инкрементировала `"nodeID" "int"`, и не регистрировала `"element" "<new_uuid>"` в `CMapGroup.children` и `CVisibilityMgr.nodes` / `hiddenFlags`.
  3. Старая реализация `remove_map_entity` удаляла только текстовый блок `"CMapEntity"`, оставляя висячие ссылки `"element" "<removed_uuid>"` в `children` и `CVisibilityMgr.nodes`, что нарушало равенство длин `nodes` и `hiddenFlags`.
- **Корневая причина:** Первоначальный прототип писался на Mac без реального образца `template_map.vmap` из `dmxconvert.exe`.
- **Примененное решение:**
  1. В `add_map_entity` все вхождения `"id" "elementid" "..."` внутри клонируемого блока заменяются на уникальные `uuid.uuid4()`, `nodeID` выставляется в `max(nodeID) + 1`, блок `"CMapEntity"` вставляется на верхнем уровне через `\n\n`, а ссылка `"element" "<new_uuid>"` добавляется с валидным синтаксисом запятых в родительский `"children" "element_array"` и в `CVisibilityMgr.nodes` (с синхронным добавлением `"0"` в `CVisibilityMgr.hiddenFlags`).
  2. В `remove_map_entity` вместе с блоком `"CMapEntity"` удаляются ссылки `"element" "<removed_uuid>"` из `children` и `CVisibilityMgr.nodes`, а также соответствующий элемент по индексу из `CVisibilityMgr.hiddenFlags` с сохранением валидного синтаксиса запятых.
  3. **Ограничение `remove_map_entity`:** Инструмент `remove_map_entity` рассчитан на точечные сущности (point entities с пустым массивом `"children" "element_array"`). При удалении составных/объемных сущностей с дочерними элементами вложенные элементы (`children`) рекурсивно не обрабатываются и не удаляются из `CVisibilityMgr`.
  4. Подтверждено прогоном реального `dmxconvert.exe` в бинарный `.vmap` (код возврата `0`) и компиляцией через `resourcecompiler.exe` (код возврата `0`).
- **Правило предотвращения:** Любые модификации `.vmap` в формате `keyvalues2` проверять на инварианты: 100% уникальность всех `elementid`, присутствие/отсутствие UUID в `children` и `CVisibilityMgr.nodes`, равенство `len(nodes) == len(hiddenFlags)` и код возврата `0` от `dmxconvert.exe`.

### [2026-10-22 13:13:05] Компонент: `vmap_builder.py` (🟠 6: Флаги компиляции карты `.vmap` в `resourcecompiler.exe`)
- **Симптом / Ошибка:** Вызов `resourcecompiler.exe -i map.vmap -v` без явных флагов стадий сборки карты не гарантирует быструю сборку всех игровых компонентов (`GridNav`, физики, мира и сущностей) без долгого запекания рейтрейс-лайтмап (`vrad3`).
- **Корневая причина:** В `tools\hammer.dll` и `resourcecompiler.dll` пресеты сборки карты передают специализированные флаги в `resourcecompiler.exe`.
- **Примененное решение:**
  - **Найдены в `tools\hammer.dll` и `resourcecompiler.dll`, ПОДТВЕРЖДЕНЫ реальной компиляцией (`return_code = 0`, время сборки 8.6 сек, создаёт `maps/<map>.vpk` со всеми 12 ресурсами, включая `maps/<map>.vmap_c`, `maps/<map>.gnv`, `world.vwrld_c`, `world_physics.vphys_c`, `entities/default_ents.vents_c`):**
    `-fshallow -v -world -phys -gridnav -entities -nolightmaps`
  - **Найдены в `tools\hammer.dll` / `resourcecompiler.dll`, НЕ подтверждены реальной компиляцией (не используются в `vmap_builder.py`):**
    `-bakelighting`, `-lightmapVRadQuality 0/1/2`, `-lightmapMaxResolution`, `-lightmapDeterministicCharts`, `-lightmapDisableFiltering`, `-disableLightingCalculations`, `-rebake_surfacegraph`, `-deformables`, `-tileMeshBaseGeometry`, `-vis`, `-lod`, `-nav`.
- **Правило предотвращения:** Для автоматической сборки кастомных карт в `compile_addon_resource` всегда использовать подтвержденный набор флагов Fast Compile: `-fshallow -v -world -phys -gridnav -entities -nolightmaps`.

### [2026-10-22 13:13:10] Компонент: `netcon_bridge.py` (🔴 3 & 🔴 4: Порт NetCon `2121` и полнота поиска в `verify_vscript_api`)
- **Симптом / Ошибка:**
  1. Порт `29000` конфликтует с бинарным протоколом `VConsole2`, который автоматически запускается вместе с `-tools`.
  2. `verify_vscript_api` вызывал `run_console_command`, который обрезал вывод `script_help2` до последних 50 строк (`console_tail`) до фильтрации по `search_term`.
- **Корневая причина:** Неучтенное поведение `vconsole2.exe` на порту `29000` и преждевременный срез массива строк.
- **Примененное решение:** Дефолтный порт `DEFAULT_NETCON_PORT` изменен на `2121`. В `verify_vscript_api` фильтрация по подстроке `search_term.lower()` выполняется по всему буферу ответа сокета (с резервным чтением `game/dota/console.log`) до обрезки до 50 совпадений.
- **Правило предотвращения:** Запускать Dota 2 Workshop Tools с параметрами `-tools -netconport 2121 -console -condebug`. Никогда не обрезать сырой консольный вывод до применения поискового фильтра.

### [2026-10-22 13:13:15] Компонент: `config.py`, `addon_manager.py`, `vpk_explorer.py`, `asset_inspector.py`, `DOTA2_741_REFERENCE.md` (🟠 5, 7, 8, 9, 10, 11)
- **Симптом / Ошибка:**
  - 🟠 5: `create_or_configure_addon` перезаписывал `addoninfo.txt` с нуля;
  - 🟠 7: Отсутствовал поиск имен звуковых событий внутри `.vsndevts_c` для `EmitSoundOn`;
  - 🟠 8: В `config.py` чтение `InstallPath` и `SteamPath` из реестра находилось в одном `try`-блоке;
  - 🟠 9: Ошибки внутри `auto_precache.lua` глушились немым `pcall`;
  - 🟠 10: Регулярное выражение для `Control Points` в `inspect_particle` пропускало поле `m_nOverrideCP` (обнаружено на реальном дампе `pudge_meathook_dragonclaw.vpcf_c`, где `m_nOverrideCP = 2`);
  - 🟠 11: В `DOTA2_741_REFERENCE.md` `ent_dota_shop` была указана как точечная сущность.
- **Корневая причина:** Отсутствие проверки на реальных дампах `Source2Viewer-CLI.exe` и файлах шаблона Dota 2 на этапе прототипирования.
- **Примененное решение:**
  - 🟠 5: `addoninfo.txt` парсится через `vdf.loads`, сохраняя пользовательские ключи;
  - 🟠 7: Добавлен инструмент `search_sound_events(query, file_filter, limit)`, извлекающий имена событий из блока `DATA` файлов `soundevents/**/*.vsndevts_c`;
  - 🟠 8: Запросы `InstallPath` и `SteamPath` в `config.py` разделены на независимые `try..except`;
  - 🟠 9: В `addon_game_mode.lua` используется `xpcall` с печатью `[MCP Precache Error]` в консоль;
  - 🟠 10: В `inspect_particle` расширено регулярное выражение для всех `m_n*ControlPoint*` и `m_n*CP*` (теперь для `pudge_meathook_dragonclaw.vpcf` корректно извлекаются CP `[1, 2, 3]`), а в `inspect_model` добавлено извлечение привязки `attach_*` к костям (`attachment_bones`);
  - 🟠 11: `ent_dota_shop` убрана из таблицы точечных сущностей в `DOTA2_741_REFERENCE.md` с примечанием о `trigger_shop` и `GameRules:SetUseUniversalShopMode(true)`.
- **Правило предотвращения:** Все регулярные выражения парсеров ресурсов сверять по эталонным дампам в `docs/reference_samples/`.

### [2026-10-22 13:42:00] Компонент: `addon_manager.py` (`create_or_configure_addon`: аддон не отображался в списке Workshop Tools)
- **Симптом / Ошибка:** Созданный через `create_or_configure_addon` аддон `mcp_test` отсутствовал в окне выбора аддонов Dota 2 Workshop Tools (так же как системные `addon_template`, `hero_demo`, `npx_2019`, `tutorial_basics`, `tutorial_assist_game`), тогда как созданный штатной кнопкой *Create New Addon* эталонный аддон `mcp_probe` отображался.
- **Корневая причина:**
  1. При копировании папки `game/dota_addons/addon_template` копировался её `addoninfo.txt`, содержавший `"IsTemplate" "1"` и `"IsPlayable" "0"`. После фикса 🟠 5 (сохранение существующих ключей `addoninfo.txt`) `create_or_configure_addon` читал скопированный из шаблона `addoninfo.txt`, оставлял `"IsTemplate" "1"` и из-за `addon_dict.get("IsPlayable", "1")` сохранял `"IsPlayable" "0"`. Любой аддон с `"IsTemplate" "1"` принудительно скрывается лаунчером Workshop Tools.
  2. Кроме того, при `shutil.copytree(template_game, game_addon)` копировался файл `readonly_tools_asset_info.bin` (5288 байт), который штатная кнопка *Create New Addon* в новых аддонах (`mcp_probe`) не создаёт, и в предкомпилированных `.vtex_c`/`.vpcf_c` внутри `game/dota_addons/addon_template` в метаданных `m_SearchPath` оставалась строка `dota_addons/addon_template` (тогда как *Create New Addon* перекомпилирует их под `dota_addons/<new_addon>`).
- **Примененное решение:**
  1. В `create_or_configure_addon` принудительно удаляются ключи `"IsTemplate"` / `"HideInTools"` из `addoninfo.txt`, а `"IsPlayable"` всегда устанавливается в `"1"`.
  2. Из `game/dota_addons/<addon>` удаляется унаследованный от шаблона `readonly_tools_asset_info.bin`.
  3. Добавлена поддержка чтения `addoninfo.txt` с заголовком `<!-- kv3 ... -->` (который создаёт кнопка *Create New Addon*).
- **Правило предотвращения:** Никогда не оставлять `"IsTemplate" "1"`, `"IsPlayable" "0"` или `readonly_tools_asset_info.bin` при клонировании `addon_template`.

### [2026-10-22 14:33:00] Компонент: `dota2.exe` / Windows Registry (`AppCompatFlags\Layers`) (Ошибка `Failed to launch` при нажатии *Launch Tools*)
- **Симптом / Ошибка:** При нажатии кнопки *Launch Tools* в окне выбора аддона (`dota2cfg.exe`) появлялось окно с ошибкой `Failed to launch: "<dota_path>\game\bin\win64\dota2.exe" -addon <addon> -tools -steam`, хотя обычная Dota 2 из Steam запускалась нормально.
- **Корневая причина:** В реестре совместимости Windows (`HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers`) для `dota2.exe` стоял флаг `~ RUNASADMIN` («Запускать эту программу от имени администратора»). Лаунчер `dota2cfg.exe` работает без прав администратора и вызывает `CreateProcessW` для запуска `dota2.exe`, что приводит к системной ошибке Windows `ERROR_ELEVATION_REQUIRED` (`WinError 740`). Обычный же клиент Steam использует `ShellExecuteExW`, который запрашивает повышение прав через UAC.
- **Примененное решение:** Снята галочка «Запускать эту программу от имени администратора» (`~ RUNASADMIN`) со свойств `dota2.exe` (и перезапущен Antigravity без прав администратора).
- **Правило предотвращения:** Не устанавливать флаг `RUNASADMIN` на `dota2.exe` (или `dota2cfg.exe`), чтобы дочерние процессы Workshop Tools запускались через `CreateProcessW` без `ERROR_ELEVATION_REQUIRED`.

### [2026-10-22 14:33:10] Компонент: `server.py` (Несовместимость импорта `FastMCP` в пакете `mcp >= 2.0`)
- **Симптом / Ошибка:** При старте MCP-сервера (`python -m src.dota2_mcp.server`) возникала ошибка `ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where FastMCP was renamed to MCPServer (from mcp.server.mcpserver import MCPServer)`, из-за чего `dota2-workshop-mcp` падал при инициализации в Antigravity.
- **Корневая причина:** В `requirements.txt` было указано `mcp>=1.2.0`, и `pip` установил `mcp 2.3.0`, где `FastMCP` переименован в `mcp.server.mcpserver.MCPServer`.
- **Примененное решение:** В `src/dota2_mcp/server.py` добавлен совместимый импорт `from mcp.server.mcpserver import MCPServer as FastMCP` (с фоллбэком на `mcp.server.fastmcp` для `mcp 1.x`).
- **Правило предотвращения:** Всегда проверять запуск `python -m src.dota2_mcp.server` тестовым JSON-RPC запросом `initialize` перед подключением в `mcp_config.json`.

### [2026-10-22 15:00:41] Компонент: `src/dota2_mcp/vpk_explorer.py (get_base_dota_definition, _load_vpk_kv_dict)`
- **Симптом / Ошибка:** get_base_dota_definition('ability', 'lina_light_strike_array') failed with 'vdf.parse: expected openning bracket (<StringIO>, line 97)', and get_base_dota_definition('hero', 'npc_dota_hero_lina') returned 'Entry not found in scripts/npc/npc_heroes.txt'.
- **Корневая причина:** 1) npc_abilities.txt (line 97: \"default_attack\"\\n\\t\"\") and items.txt (line 3524: \"ItemRequirements\"\\n\\t\\t\"\") contain multiline key-scalar pairs that python-vdf rejects. 2) In Dota 2 7.41+, npc_heroes.txt only contains #base directives pointing to scripts/npc/heroes/npc_dota_hero_*.txt, and each hero file nests its abilities inside \"npc_dota_hero_<name>\" -> \"AbilityDefinitions\" instead of top-level keys.
- **Примененное решение:** 1) In _load_vpk_kv_dict, collapsed multiline key-scalar pairs via regex before calling vdf.loads and guarded against malformed VPK files. 2) Added _extract_abilities_from_hero_kv to read nested Hero.AbilityDefinitions in scripts/npc/heroes/npc_dota_hero_*.txt and extended get_base_dota_definition to search scripts/npc/heroes/*.txt for both category='ability' and category='hero'.
- **Правило предотвращения:** Never assume Valve KeyValues files put key and scalar value on the same line or that hero abilities live at the top level of npc_abilities.txt; in Dota 2 7.41+ both hero definitions and nested AbilityDefinitions live inside scripts/npc/heroes/npc_dota_hero_*.txt.

### [2026-10-22 15:03:40] Компонент: `src/dota2_mcp/netcon_bridge.py (verify_vscript_api)`
- **Симптом / Ошибка:** verify_vscript_api returned matches_count: 0 for valid methods like SetLevel, GetSpecialValueFor, GetGameModeEntity, and SetCustomGameForceHero even though script_help2 printed them to console.log.
- **Корневая причина:** Dota 2's NetCon TCP socket drops output after ~3,629 lines of a single command burst (around CDOTABaseAbility:GetAbilityTargetFlags alphabetically), while console.log receives the entire ~12,000-line script_help2 dump; scanning only the last 5,000 lines of console.log missed classes alphabetically between CDOTABaseAbility:G* and CScriptHeroList.
- **Примененное решение:** Increased console.log fallback scan window in verify_vscript_api from 5,000 lines to 25,000 lines so all script_help2 classes/methods/enums (which span ~12,000 lines per dump) are captured when NetCon TCP socket truncates at ~3,629 lines.
- **Правило предотвращения:** Never assume NetCon TCP socket returns the full ~12,000-line output of script_help2 or that 5,000 lines of console.log are enough to cover a full script_help2 dump.

### [2026-10-22 19:13:05] Компонент: `src/dota2_mcp/addon_manager.py (create_or_configure_addon)`
- **Симптом / Ошибка:** A freshly created addon immediately fails validate_and_sync_precache (ok:false) with 'OBSOLETE Source 1 resource/flash3 directory detected'.
- **Корневая причина:** shutil.copytree copies addon_template's game/resource/flash3/custom_ui.txt into the new addon.
- **Примененное решение:** create_or_configure_addon now removes game/<addon>/resource/flash3 right after creating a new addon from the template (existing addons are not touched).
- **Правило предотвращения:** After copying addon_template, strip every template artifact that our own validator flags (IsTemplate, readonly_tools_asset_info.bin, resource/flash3); a fresh addon must pass validate_and_sync_precache with ok:true.

### [2026-10-22 19:53:08] Компонент: `src/dota2_mcp/vmap_builder.py (compile_addon_resource)`
- **Симптом / Ошибка:** compile_addon_resource returned ok:true for a map while the log said 'Write ...\maps\lab.vpk Failed!' — the new map was silently not written.
- **Корневая причина:** resourcecompiler.exe exits with code 0 even when it cannot write the output VPK; it was locked by Dota 2 with the same map loaded. ok was based on the return code only.
- **Примененное решение:** compile_addon_resource now scans the log for 'Write ... Failed!' lines, returns ok:false with write_failures and a hint to run 'disconnect' first.
- **Правило предотвращения:** Never trust resourcecompiler's exit code alone; check its log for write failures. Run 'disconnect' in Dota before recompiling a map that is currently loaded.

### [2026-10-22 20:19:50] Компонент: `src/dota2_mcp/addon_manager.py (validate_and_sync_precache, icon compile)`
- **Симптом / Ошибка:** Custom item icon panorama/images/items/mcp_void_shard.png was never compiled: 'Failed to find compiler for file ...png', validate returned ok:false.
- **Корневая причина:** resourcecompiler.exe cannot compile a bare .png; Panorama images are built only as dependencies of a layout (.xml) that references them. Tools mode does not compile them on demand either.
- **Примененное решение:** validate_and_sync_precache now writes content/.../panorama/layout/custom_game/mcp_auto_icons.xml referencing every .png under panorama/images and compiles it; each icon becomes <name>_png.vtex_c. Stale icons (png newer than vtex_c) are rebuilt.
- **Правило предотвращения:** Compile Panorama images through a referencing layout, never the .png directly; verify the expected _png.vtex_c exists and is newer than the source.

### [2026-10-22 20:19:50] Компонент: `src/dota2_mcp/vpk_explorer.py (get_base_dota_definition, category item)`
- **Симптом / Ошибка:** get_base_dota_definition('item', 'item_blink') returned 'not found' for every stock item.
- **Корневая причина:** items.txt uses CRLF line endings; the multiline-scalar fix regex ('$' after the value) never matched before '\r', so python-vdf failed on '"ItemRequirements"\n""' and the parse error was swallowed (empty dict).
- **Примененное решение:** Normalize CRLF to LF before applying the multiline-scalar regex in _load_vpk_kv_dict.
- **Правило предотвращения:** Normalize line endings before regex-based KV cleanup; never silently return {} on a parse error of a stock file — check all four categories with a known name after parser changes.

### [2026-10-23 11:27:51] Компонент: `src/dota2_mcp/addon_manager.py (validate_and_sync_precache, sound events)`
- **Симптом / Ошибка:** Sound events used by name in Lua/KV (EmitSoundOn("Hero_X.Y"), custom events) were never precached; typos in sound names went unnoticed. Abilities needed a manual KV "precache" soundfile block.
- **Корневая причина:** The precache scanner only matched literal .vmdl/.vpcf/.vsndevts paths; there was no mapping from an event name to its .vsndevts file.
- **Примененное решение:** vpk_explorer.get_sound_event_index decompiles all 946 stock soundevents/*.vsndevts_c in one Source2Viewer-CLI call (~2 s) and caches name->file JSON per VPK version (.cache/sound_events). validate_and_sync_precache resolves every Lua/KV string literal against this index plus the addon's own content/soundevents/*.vsndevts, precaches the files, and reports unknown_sound_events (names passed to EmitSound*/StopSound* found nowhere; ok:false).
- **Правило предотвращения:** Every resource referenced by name (sounds, units) must be resolved to a file by the precache tool; unresolvable names inside Emit/Stop sound calls are errors, not silence.

### [2026-10-23 11:27:51] Компонент: `src/dota2_mcp/vmap_builder.py (compile_addon_resource, .vsndevts)`
- **Симптом / Ошибка:** compile_addon_resource on a custom soundevents/*.vsndevts reported 'OK: 1 compiled' but no sounds/*.vsnd_c was produced; the referenced .wav files stayed uncompiled.
- **Корневая причина:** resourcecompiler.exe does not compile audio referenced by a .vsndevts as dependencies (unlike Panorama layouts/images). A .wav compiles fine when passed directly.
- **Примененное решение:** After compiling a .vsndevts, compile_addon_resource compiles every referenced "sounds/....vsnd" from its .wav/.mp3 source in content/ and returns sound_sources_compiled; missing sources give ok:false with missing_sound_sources.
- **Правило предотвращения:** After compiling any resource, verify the expected compiled children exist in game/ (here sounds/*.vsnd_c); do not assume the compiler follows references.

### [2026-10-23 11:27:51] Компонент: `src/dota2_mcp/vpk_explorer.py (search_sound_events)`
- **Симптом / Ошибка:** search_sound_events could miss real events: only the first 60 of 946 .vsndevts_c files were scanned (each decompiled separately, slow).
- **Корневая причина:** Per-file decompilation with a hard cap of 60 files to keep the call fast.
- **Примененное решение:** search_sound_events now answers from the cached full sound event index (all 946 files, ~105 K events, lookup ~0.1 s); the old per-file scan remains as a fallback when the index cannot be built.
- **Правило предотвращения:** Search tools must cover the whole data set; build a one-time cache instead of capping the scan.

### [2026-10-23 14:34:55] Компонент: `upsert_localization (addon_manager.py)`
- **Симптом / Ошибка:** Found in code review during stage 8: (1) an existing addon_<lang>.txt saved as UTF-8 without BOM was decoded as UTF-16 first, which can 'succeed' with garbage that parses to an empty token block, so the rewrite would drop every existing token; (2) values with a line break were written as raw multi-line strings (vdf unescapes \n on read, so each round trip turned \n into a real newline); (3) nothing reported tokens missing in other languages (addon_game_name was English-only in mcp_lab).
- **Корневая причина:** Encoding chosen by trial order instead of the BOM; the first parse without exception was accepted even when no "lang" block was found; only quotes were escaped on write; no cross-language comparison.
- **Примененное решение:** New _read_loc_tokens: encoding by BOM (UTF-8 BOM / UTF-16 BOM, else UTF-8 then UTF-16-LE) and a result is accepted only when a "lang" block exists. Write escapes newlines as \n. Response adds missing_in_this_language / not_yet_in_other_languages. validate_and_sync_precache got a 'localization' section (untranslated names, unknown #tokens, missing per language, bad %vars%). Tested on synthetic files and on mcp_lab.
- **Правило предотвращения:** When reading text files with several possible encodings, pick by BOM and validate the parsed structure before trusting it; never rewrite a file from a parse that found nothing. After adding strings, check the localization section of validate_and_sync_precache.

### [2026-10-25 16:01:13] Компонент: `mcp_lab addon_game_mode.lua + require of a module defining game mode methods`
- **Симптом / Ошибка:** Script Runtime Error: mcp_lab_hunters.lua:32: attempt to index global 'CAddonTemplateGameMode' (a nil value); whole addon_game_mode failed to load.
- **Корневая причина:** addon_game_mode.lua runs in its own script scope: globals it defines (the game mode class) are not visible to files loaded with require.
- **Примененное решение:** The module builds a local method table and returns it; addon_game_mode.lua copies the methods onto CAddonTemplateGameMode (for name, method in pairs(require("mcp_lab_hunters")) do ... end).
- **Правило предотвращения:** Never reference addon_game_mode globals from a required file; pass them in or return a table to merge. Engine globals (GameRules, Convars, LinkLuaModifier) are fine.

### [2026-10-25 16:01:13] Компонент: `src/dota2_mcp read_latest_console_log (errors_and_warnings)`
- **Симптом / Ошибка:** After a relaunch, errors_and_warnings still listed a Lua error from the previous (already fixed) launch, also in grep mode; looks like the current run is broken and costs context.
- **Корневая причина:** Errors are collected from the whole console.log session, not from the latest game launch.
- **Примененное решение:** Not fixed yet (logged as idea). Workaround: judge the current run by tail lines after the last '[MCP_LAB] Initializing game mode...' line.
- **Правило предотвращения:** When reading errors after a relaunch, check that they come after the latest launch marker before treating them as current.

### [2026-10-25 16:23:20] Компонент: `mcp_lab mcp_lab_autotest9 (repeat run)`
- **Симптом / Ошибка:** Second autotest run in a row failed only 'killer': Kill(hero, lina) via ApplyDamage did nothing, hero stayed alive, no entity_killed.
- **Корневая причина:** The previous run ends with RespawnHero, so the player's hero stands in the fountain and has modifier_fountain_invulnerability (several stacks); removing modifier_invulnerable is not enough. Also the old 7 s invulnerability ran out before the kill step once the test got longer.
- **Примененное решение:** Test Kill() uses damage_flags = DOTA_DAMAGE_FLAG_BYPASSES_INVULNERABILITY; start-of-test invulnerability raised to 12 s.
- **Правило предотвращения:** Autotests must pass twice in a row: run every autotest a second time without relaunch. Test kills use BYPASSES_INVULNERABILITY; protection durations must cover the whole test.

### [2026-10-25 17:00:07] Компонент: `mcp_lab Panorama cutscene (stage 10)`
- **Симптом / Ошибка:** During the cutscene the rift HUD panel and the overhead charges stayed on screen (seen on a take_game_screenshot frame), although the probe reported the stock HUD hidden.
- **Корневая причина:** $.GetContextPanel() is the layout's own CustomUIElement, not a child of it; the code walked one level too high and hid siblings of CustomUIContainer_Hud instead of the other custom layouts.
- **Примененное решение:** Hide the siblings of $.GetContextPanel() inside its parent (CustomUIContainer_Hud) plus HUDElements; autotest asserts hidden == 3.
- **Правило предотвращения:** For visual features always look at a real frame (take_game_screenshot); a probe only proves what the code thinks it did. Assert exact counts of hidden panels.

### [2026-10-25 17:00:07] Компонент: `mcp_lab localization (stage 9 leftovers)`
- **Симптом / Ошибка:** validate_and_sync_precache reported 5 tokens missing in addon_english.txt (Trophies, Hunters' power, Last killer, hunter power modifier tooltip).
- **Корневая причина:** Stage 9 added HUD/modifier texts only to addon_russian.txt; the English pass was skipped.
- **Примененное решение:** Added the 5 English strings via upsert_localization.
- **Правило предотвращения:** Upsert every new token in all addon languages in the same step and read missing_in_language from validate_and_sync_precache before finishing a stage.

### [2026-10-25 17:37:13] Компонент: `netcon_bridge.verify_vscript_api (API cache)`
- **Симптом / Ошибка:** verify_vscript_api found nothing for SetGameWinner, SetPreGameTime, PlayerHasCustomGameHostPrivileges and every other CDOTAGameRules method, although they exist and work at runtime.
- **Корневая причина:** The cached script_help2 dump for build 6967 lacked the whole CDOTAGameRules class (148 functions) while still holding 1815 functions, so the only completeness check (>= 500 functions) passed and the partial dump was cached for the build.
- **Примененное решение:** Cache rebuilt with refresh=True (1987 functions, CDOTAGameRules present). The dump is now cached only if it also contains the core classes CDOTAGameRules, CDOTABaseGameMode, CDOTA_BaseNPC and CDOTA_PlayerResource.
- **Правило предотвращения:** If verify_vscript_api finds no match for a well-known class or method, check the class itself (e.g. "CDOTAGameRules:") and rebuild the cache with refresh=True before concluding the API does not exist.

### [2026-10-25 17:37:13] Компонент: `addon_manager.validate_and_sync_precache (localization check)`
- **Симптом / Ошибка:** unknown_token_references reported "#mcp_lab_lobby_look_ (mcp_lab_end.js)" for $.Localize( "#mcp_lab_lobby_look_" + stats.look ), a token built at runtime.
- **Корневая причина:** LOC_JS_RE / LOC_LUA_RE treated any quoted "#token" literal as a full token, including a prefix that is concatenated with a variable.
- **Примененное решение:** Negative lookahead: a literal followed by "+" (JS) or ".." (Lua) is ignored as a dynamic prefix. Takes effect after the MCP server restarts.
- **Правило предотвращения:** Dynamic token names cannot be checked statically; keep every possible full token in the localization files and test them live (stage 8 probe pattern).

### [2026-10-25 18:01:49] Компонент: `prepare_map_from_template (vmap_builder.py)`
- **Симптом / Ошибка:** source_template="dota" silently copied template_map; with a real 300 MB map the conversion ended with WinError 32 and a leftover .kv2.vmap file.
- **Корневая причина:** Stock sources in content/dota/maps were not searched and unknown names fell back to template_map; shutil.move on Windows = copy + unlink, the unlink of the big temp file was blocked by another process.
- **Примененное решение:** Added content/dota/maps/<name>.vmap as a candidate, fallback to template_map only when it is requested; os.replace with 10 retries; dmxconvert timeout 600 s, map compile timeout 1800 s.
- **Правило предотвращения:** Never fall back silently to a different template; use atomic os.replace for big files on Windows.

### [2026-10-25 20:17:25] Компонент: `prepare_map_from_template (stock map copy)`
- **Симптом / Ошибка:** m1_dota (copy of stock dota.vmap) launches, but the minimap is plain grey (owner check 2026-10-25).
- **Корневая причина:** The minimap comes from resource/overviews/<map>.txt; a stock map copied under a new name has no overview file.
- **Примененное решение:** prepare_map_from_template now writes game/dota_addons/<addon>/resource/overviews/<map>.txt from the stock resource/overviews/<source>.txt (root key renamed, stock materials reused). Screenshot after relaunch: full Dota minimap.
- **Правило предотвращения:** When a map is renamed or copied, check its minimap overview .txt exists under the new map name.

### [2026-10-25 20:25:14] Компонент: `mcp_lab stage 12 (Panorama events from mcp_lab_mode1.lua)`
- **Симптом / Ошибка:** mcp_lab_zone / mcp_lab_video events sent from Lua get no JS reaction: "Зона" row stays "—", Movie panel stays hidden, no ack (3 attempts). Other HUD events (mcp_lab_hud) work.
- **Корневая причина:** Not found yet. Fixed on the way: CustomGameEventManager:RegisterListener called while the file is required (before Activate) never fires -> moved to first use (now logged as Registered). JS was recompiled by the game; XML row appears.
- **Примененное решение:** Open. Next: check that the running HUD JS has OnZone (e.g. $.Msg in OnZone), check custom_net/event names, try GameEvents.Subscribe inside the existing init vs a fresh Dota restart.
- **Правило предотвращения:** Register custom game event listeners inside InitGameMode/Activate or lazily, never at require time.

### [2026-10-25 20:54:17] Компонент: `mcp_lab stage 12 (Panorama events from mcp_lab_mode1.lua) — FIXED`
- **Симптом / Ошибка:** Follow-up to the 20:25:14 entry: "Зона" row stayed "—", webm not shown.
- **Корневая причина:** Not isolated; after a fresh Dota restart events arrive (likely stale HUD JS in the running session). Zone code also could run before the hero existed.
- **Примененное решение:** $.Msg in OnZone, nil-hero guard, fallback knock-out directions; restart Dota. Zone autotest PASS, row updates, stock/small/29 MB webm play (screenshots).
- **Правило предотвращения:** If a custom game event reaches Lua listeners but not JS, first restart Dota and log with $.Msg in the JS handler before changing code.

### [2026-10-25 20:54:17] Компонент: `mcp_lab stage 12 part 7 (Russian stock hero VO from Lua)`
- **Симптом / Ошибка:** Owner: mcp_lab_voice runs without Lua errors, but the heroes' laughs (CM, TA, WD, Ursa) are not heard.
- **Корневая причина:** Open. Candidates: EmitSoundOnClient with a VO line name not resolved on the client, VO volume/channel, Russian VO pack not mounted in Tools mode.
- **Примененное решение:** Open — not fixed.
- **Правило предотвращения:** For sound checks require an owner ear test; "no Lua errors" does not mean the sound played.

### [2026-10-25 20:54:17] Компонент: `mcp_lab stage 12 part 3 (old maps dota_683 / dota_685)`
- **Симптом / Ошибка:** dota_launch_custom_game with dota_683: Dota client crashed right after the match started. dota_685: map not found by name.
- **Корневая причина:** Old 6.83/6.85 maps are not compatible with the current client (683) / not shipped under that name (685).
- **Примененное решение:** None; marked "не работает", not retried to avoid crashes.
- **Правило предотвращения:** Do not launch old patch maps (dota_683/685) in live tests; use the stock dota map copy.

### [2026-10-30 22:24:15] Компонент: `scaffold_game_element / mcp_lab stage 13 (earth rift ability hotkey)`
- **Симптом / Ошибка:** Owner check 2026-10-30: the scaffolded ability "Разлом земли" works (icon, sound, particle, tooltip), but no hotkey is bound to its button.
- **Корневая причина:** Open. Likely the ability is added at runtime (AddAbility in mcp_lab_autotest13) into a slot outside the hotkeyed slots, or hidden/extra slot index.
- **Примененное решение:** Open — not fixed.
- **Правило предотвращения:** When adding an ability at runtime, check its slot index (GetAbilityIndex) is within the hero's hotkeyed slots and test the hotkey, not only the button click.

### [2026-10-30 22:24:16] Компонент: `scaffold_game_element / mcp_lab stage 13 (earth rift particle radius)`
- **Симптом / Ошибка:** Owner check 2026-10-30: the "Разлом земли" particle (Leshrac stun) looks about 2x smaller than the damage radius.
- **Корневая причина:** Open. The scaffold sets only CP0 position; the stock particle's radius control point (see inspect_particle) is not set to the ability radius.
- **Примененное решение:** Open — not fixed.
- **Правило предотвращения:** For area abilities, inspect_particle the effect and set its radius control point from the ability radius; check the visual size with a screenshot.

### [2026-10-30 22:27:51] Компонент: `mcp_lab stage 13 hotkey + scaffold particle radius — FIXED (stage 14)`
- **Симптом / Ошибка:** Follow-up to the 2026-10-30 22:24 entries: mcp_rift_quake had no hotkey; Leshrac split earth particle ~2x smaller than radius 325.
- **Корневая причина:** AddAbility at runtime puts the ability after the talents (slot 20, no hotkey; engine warns "unhide in a slot > 5"). The particle reads its size from CP1 (inspect_particle: control_points_used [1]); only CP0 was set.
- **Примененное решение:** Autotest swaps the ability into the empty D slot (SwapAbilities with mcp_empty1, only if GetAbilityIndex() > 5 — swapping again moves it back to 20). Ability sets CP1 = Vector(radius, radius, radius). scaffold_game_element now runs inspect_particle and emits the CP1 radius line when the particle reads CP1 and the spec has radius. Autotest PASS 7/7, slot 3 (D), screenshot: effect covers the radius.
- **Правило предотвращения:** Runtime-added abilities: move into an empty slot 0-5 and guard against swapping twice. Area particles: set the CP that inspect_particle reports besides CP0 (usually CP1 = radius) and check size on a screenshot.

### [2026-10-30 23:44:51] Компонент: `mode-1 addon (custom game) — hero spawn`
- **Симптом / Ошибка:** No hero spawned; console: Unrecognized custom hero name 'npc_dota_hero_<custom>'. Game state ran, but the hero-ready print never appeared.
- **Корневая причина:** npc_heroes_custom block npc_dota_hero_<custom> uses override_hero npc_dota_hero_tidehunter; such a hero keeps the template unit name, so SetCustomGameForceHero and the npc_spawned name check with the custom name never match.
- **Примененное решение:** Force and compare npc_dota_hero_tidehunter (force hero + spawn check). Hero spawns, autotest PASS.
- **Правило предотвращения:** With override_hero, force/compare the template hero name; the block name is only a label.

### [2026-10-30 23:44:51] Компонент: `mode-1 addon (custom game) — CastFilterResultTarget`
- **Симптом / Ошибка:** Repeated client Script Runtime Error: <ability>.lua:13 attempt to call method 'GetAbilityTargetTeam' (a nil value).
- **Корневая причина:** CastFilterResultTarget also runs on the client VM, where C_DOTA_Ability_Lua has no GetAbilityTargetTeam/Type/Flags (server-only).
- **Примененное решение:** UnitFilter with spelled-out constants DOTA_UNIT_TARGET_TEAM_ENEMY, HERO + BASIC, FLAG_NONE (UnitFilter confirmed on client via cl_script_help2). Relaunch + autotest: 0 Lua errors.
- **Правило предотвращения:** In cast filters use only client-available API; check with cl_script_help2 <name>.

### [2026-10-31 00:08:52] Компонент: `mode-1 addon (respawn)`
- **Симптом / Ошибка:** After the first death the player hero was ignored by AI heroes and creeps (no more deaths); FindUnitsInRadius returned 0 next to it.
- **Корневая причина:** Respawn at the fountain applies modifier_fountain_invulnerability (stacked x4); moving the hero away with FindClearSpaceForUnit does not remove it.
- **Примененное решение:** Remove every modifier_fountain_invulnerability instance in the respawn handler right after the move.
- **Правило предотвращения:** When a mode respawns heroes away from the fountain, strip fountain invulnerability after the move and assert it in the autotest.

### [2026-10-31 00:08:52] Компонент: `mode-1 addon (AI ward)`
- **Симптом / Ошибка:** Ownerless AI hero ordered CastAbilityOnPosition with item_ward_observer: the ward is never placed, item stays (charges 1, castable).
- **Корневая причина:** Unknown (open). Not the target point under a unit and not overriding orders (both excluded).
- **Примененное решение:** None yet (2 attempts).
- **Правило предотвращения:** Next try: read the cast failure in the console, or spawn npc_dota_observer_wards with CreateUnitByName instead of casting.

### [2026-10-31 13:51:35] Компонент: `mode-1 (private addon): unit-target eat ability vs zone knockback`
- **Симптом / Ошибка:** Eat ability on a low-HP enemy hero plays the move/cast start but the hero is never eaten.
- **Корневая причина:** Target stood just outside the small zone: the caster walked to it, the zone knockback threw it back, the order never completed. Also the retreating AI regenerated 8 %/s and rose above the HP threshold before the caster got in range (the filter is rechecked).
- **Примененное решение:** Zone widened by walkable path (pit + river), hunters no longer flee/regenerate in chapter 1, threshold 25 %. Verified by a real CastAbilityOnTarget order with the AI on.
- **Правило предотвращения:** Test unit-target abilities with a real order (not OnSpellStart) and with the target near a zone border and under its live AI.
