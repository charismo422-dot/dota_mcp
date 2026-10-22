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
