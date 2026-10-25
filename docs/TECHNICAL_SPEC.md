# Техническая спецификация проекта `dota_mcp` (Dota 2 Workshop Tools MCP Server)

> **Статус:** ✅ **Фаза 0 полностью пройдена на Windows-ПК с установленной Dota 2.** Все 19 инструментов фазы 0 MCP-сервера протестированы на реальных бинарниках (`dmxconvert.exe`, `resourcecompiler.exe`, `Source2Viewer-CLI.exe`) и живом подключении к движку по NetCon (`127.0.0.1:2121`). Тестовый аддон-песочница: `mcp_test`.

## 1. Назначение системы
`dota_mcp` — специализированный сервер Model Context Protocol (MCP) и набор правил/навыков для ИИ-агента Antigravity, позволяющий создавать, модифицировать, компилировать и отлаживать кастомные игры (Custom Games) в **Dota 2 Workshop Tools** на ОС Windows полностью автономно по текстовому запросу пользователя.

---

## 2. Архитектура и технологический стек

### 2.1. Стек разработки кастомок (Target Stack)
- **Логика (VScripts):** Lua 5.1/5.2 (штатный движок Source 2 `game/dota_addons/<addon>/scripts/vscripts/`).
- **Данные (DataDriven / KV):** Valve KeyValues (`.txt` / `.kv` в `game/dota_addons/<addon>/scripts/npc/`).
- **Интерфейс (UI):** Panorama UI (`.xml`, `.css`, `.js` в `content/dota_addons/<addon>/panorama/`).
- **Карты (Maps):** Source 2 `.vmap` (редактирование в текстовом формате `keyvalues2` (`format vmap 40`) через штатный `dmxconvert.exe`, компиляция в `maps/<map>.vpk` с `.vmap_c` и `.gnv` через `resourcecompiler.exe`).
- **Локализация:** `game/dota_addons/<addon>/resource/addon_<language>.txt` (по умолчанию `UTF-16` / UCS-2 LE с BOM, как в штатном `addon_template`).

### 2.2. Стек MCP-сервера (`dota2_mcp/`)
- **Язык:** Python 3.10+
- **Фреймворк MCP:** `mcp>=2.3.0,<3.0.0` (`MCPServer` / `FastMCP`, транспорт `stdio`)
- **Библиотеки Python:**
  - `vpk` (ValvePython) — чтение индекса и извлечение файлов из `game/dota/pak01_dir.vpk` без распаковки всего архива на диск.
  - `vdf` (ValvePython) — парсинг и сериализация файлов Valve KeyValues (`.txt`, `.kv`, `addoninfo.txt`).
- **Внешние бинарные утилиты Source 2 (входят в состав Dota 2 Workshop Tools):**
  - `<dota_path>/game/bin/win64/dmxconvert.exe` — конвертация карт `.vmap` между бинарным форматом и текстовым `keyvalues2`.
  - `<dota_path>/game/bin/win64/resourcecompiler.exe` — компиляция `.vmap` (с флагами Fast Compile `-fshallow -v -world -phys -gridnav -entities -nolightmaps`), Panorama UI, иконок и материалов в скомпилированные ассеты (`_c`).
- **Внешний CLI-инспектор скомпилированных ресурсов (`_c`):**
  - `Source2Viewer-CLI.exe` (`ValveResourceFormat` в `bin/Source2Viewer-CLI.exe`). Используется для чтения анимаций (`ACT_DOTA_*`), точек крепления (`attach_*` и костей) из `.vmdl_c`, `Control Points` из `.vpcf_c` и звуковых событий из `.vsndevts_c`.
- **Сетевой интерфейс движка (Live Engine Bridge):**
  - TCP-клиент к порту `-netconport 2121` (текстовый Telnet-поток запущенной Dota 2, не конфликтующий с портом `29000` бинарного `vconsole2.exe`) для отправки команд (`dota_launch_custom_game`, `script_reload`, `ent_find`) и чтения логов/ошибок Lua в реальном времени.

---

## 3. Структура репозитория `dota_mcp`

```text
dota_mcp/
├── AGENTS.md                                  # Единый источник правил проекта для всех ИИ-агентов
├── GEMINI.md                                  # Ссылка на AGENTS.md для Antigravity (@[AGENTS.md](./AGENTS.md))
├── CLAUDE.md                                  # Ссылка на AGENTS.md для Claude Code (@AGENTS.md)
├── README.md                                  # Документация для пользователей (EN)
├── README.ru.md                               # Документация для пользователей (RU)
├── setup.py                                   # Идемпотентный установщик окружения и генератор MCP-конфигов
├── setup.ps1                                  # PowerShell-обертка для запуска setup.py
├── requirements.txt                           # Python-зависимости (mcp>=2.3.0,<3.0.0, vpk, vdf, requests)
├── examples/
│   └── mcp_test/                              # Рабочий пример аддона со способностью «Огненное кольцо»
├── docs/
│   ├── TECHNICAL_SPEC.md                      # Полная техническая спецификация (этот документ)
│   ├── SELF_CHECK_PROTOCOL.md                 # Протокол инженерной самопроверки агента
│   ├── BUG_LOG.md                             # Журнал фиксации багов, ошибок и исправлений
│   ├── history/
│   │   └── CODE_REVIEW_TODO.md                # Архив чеклиста Фазы 0
│   └── reference_samples/                     # Эталонные дампы реальных форматов (.vmap, .vmdl_c, .vpcf_c, .vsndevts_c)
├── tests/
│   └── verify_phase0_acceptance.py            # Приёмочный автотест vmap_builder, dmxconvert и resourcecompiler
├── .agents/
│   └── skills/
│       └── dota2-custom-game-dev/
│           └── SKILL.md                       # Пошаговый алгоритм для агента по созданию кастомок
└── src/
    └── dota2_mcp/
        ├── __init__.py
        ├── server.py                          # Точка входа MCPServer и регистрация всех 20 инструментов
        ├── config.py                          # Автоопределение путей Steam, Dota 2, dmxconvert, resourcecompiler
        ├── vpk_explorer.py                    # Модуль 1: Поиск ассетов, звуковых событий и чтение базовых KV в pak01_dir.vpk
        ├── asset_inspector.py                 # Модуль 2: Инспекция .vmdl_c (анимации/attachments) и .vpcf_c (CP)
        ├── addon_manager.py                   # Модуль 3: Создание аддона, валидация KV, авто-Precache, локализация
        ├── vmap_builder.py                    # Модуль 4: Чтение/модификация .vmap через dmxconvert + компиляция
        ├── netcon_bridge.py                   # Модуль 5: TCP-мост к запущенной Dota 2 (-netconport 2121)
        └── diagnostics.py                     # Модуль 6: Самодиагностика MCP и авто-логирование багов в BUG_LOG.md
```

---

## 4. Спецификация всех 20 инструментов MCP-сервера (Tools Reference)

### Модуль 1: Поиск ассетов, звуковых событий и оригинальных скриптов (`vpk_explorer.py`)
1. `search_dota_assets(query: str, asset_type: str = "all", limit: int = 25) -> dict`
   - **Описание:** Ищет в `game/dota/pak01_dir.vpk` реальные пути к файлам по подстроке/ключевым словам.
   - **Фильтры `asset_type`:** `"model"` (`.vmdl`), `"particle"` (`.vpcf`), `"sound"` (`.vsnd` / `.vsndevts`), `"material"` (`.vmat`), `"panorama"` (`.png` / `.vsvg`), `"script"` (`.txt` / `.lua`), `"all"`.
   - **Особенность:** Автоматически убирает суффикс `_c` у возвращаемых путей, чтобы пути сразу подходили для вставки в Lua, KV и `.vmap`.
2. `search_sound_events(query: str, file_filter: str = "", limit: int = 30) -> dict`
   - **Описание:** Ищет по кэшированному индексу всех звуковых событий (`vpk_explorer.get_sound_event_index`: один вызов `Source2Viewer-CLI.exe -i pak01_dir.vpk -f soundevents/ -e vsndevts_c -d` декомпилирует все ~946 файлов за ~2 с, индекс «имя → файл» хранится в `.cache/sound_events/` и пересобирается при смене версии VPK; запасной путь — старый пофайловый поиск) точные имена звуковых событий (например, `Hero_Pudge.Attack`) для использования в `EmitSoundOn` / `StopSoundOn`, а также возвращает путь к файлу `.vsndevts` для предзагрузки (`PrecacheResource("soundfile", ...)`).
3. `get_base_dota_definition(category: str, name: str) -> dict`
   - **Описание:** Извлекает из `pak01_dir.vpk` (`scripts/npc/npc_heroes.txt`, `npc_abilities.txt`, `scripts/npc/heroes/npc_dota_hero_*.txt`, `npc_units.txt`, `items.txt`) точный блок настроек стандартного героя, способности, юнита или предмета актуальной Dota 2 (7.41+).
   - **Параметр `category`:** `"hero"`, `"ability"`, `"unit"`, `"item"`.

### Модуль 2: Глубокая инспекция моделей и партиклов (`asset_inspector.py`)
4. `inspect_model(model_path: str) -> dict`
   - **Описание:** Извлекает `.vmdl_c` из VPK (или папки аддона), декомпилирует через `Source2Viewer-CLI.exe` и возвращает список:
     - `activities`: связанные `Activity` (например, `ACT_DOTA_ATTACK`, `ACT_DOTA_DIE`, `ACT_DOTA_CAST_ABILITY_1`).
     - `attachments` и `attachment_bones`: точки крепления эффектов/оружия (например, `attach_hitloc`, `attach_attack1`) и кости, к которым они привязаны.
     - `animation_identifiers_sample`: образцы имен анимаций.
5. `inspect_particle(particle_path: str) -> dict`
   - **Описание:** Декомпилирует `.vpcf_c` и возвращает список используемых `Control Points` (`control_points_used`, включая `m_nControlPointNumber`, `m_nOverrideCP`, `m_nFirstControlPoint` и др.), дочерние эффекты (`child_particles`), `initializers` и `operators`.

### Модуль 3: Управление аддоном, KV, Precache и локализацией (`addon_manager.py`)
6. `create_or_configure_addon(addon_name: str, maps: list[str], max_players: int = 10, team_count: int = 2) -> dict`
   - **Описание:** Создает структуру нового аддона в `content/dota_addons/<addon_name>` и `game/dota_addons/<addon_name>` на базе штатного `addon_template` (удаляя `readonly_tools_asset_info.bin` и флаг `"IsTemplate"`, чтобы аддон был виден в списке Workshop Tools), обновляет `addoninfo.txt` с сохранением пользовательских ключей и возвращает таблицу маршрутизации папок.
7. `get_addon_paths(addon_name: str) -> dict`
   - **Описание:** Возвращает точные канонические пути для `game/` (исполняемые файлы Lua, KV, локализация) и `content/` (исходники `.vmap`, Panorama `.xml`/`.css`/`.js`, кастомные иконки `.png` в `spellicons/` и `items/`).
8. `validate_and_sync_precache(addon_name: str) -> dict`
   - **Описание:**
     1. Проверяет все `.txt` / `.kv` файлы в `game/dota_addons/<addon_name>/scripts/npc/` через парсер `vdf` на синтаксические ошибки и правильность префиксов `AbilityTextureName` (`item_` для предметов).
     2. Ловит ошибочно размещенные файлы (например, устаревшую папку `resource/flash3`, сырые `.png`/`.xml`/`.css`/`.js` в `game/` или `.lua` в `content/`).
     2a. Звуки по имени: каждая строка вида `Xxx.Yyy` в `.lua`/`.txt` сверяется с индексом стандартных событий и с событиями аддона из `content/<addon>/soundevents/**/*.vsndevts`; найденные `.vsndevts` попадают в `auto_precache.lua` (`soundfile`). Имена в вызовах `EmitSound*`/`StopSound*`/`StartSoundEvent*`, которых нет нигде, возвращаются в `unknown_sound_events` (`ok: false`). Поля ответа: `sound_events_resolved`, `sound_files_from_events`, `custom_sound_events`, `unknown_sound_events`.
     3. Автоматически компилирует новые и изменённые `.png` иконки из `content/.../panorama/images/` в `<name>_png.vtex_c`: генерирует скрытый макет `panorama/layout/custom_game/mcp_auto_icons.xml` со ссылками на все иконки и компилирует его `resourcecompiler.exe` (голый `.png` компилятор не принимает, картинки собираются только как зависимости макета).
     4. Сканирует все `.lua` и `.txt` файлы аддона на наличие путей `.vmdl`, `.vpcf`, `.vsndevts` и проверяет их существование в `pak01_dir.vpk`.
     5. Автоматически формирует/обновляет список `PrecacheResource` в `auto_precache.lua` и подключает его к `addon_game_mode.lua` через `xpcall` с логированием ошибок.
     6. Проверяет локализацию (поле `localization`, на общий `ok` не влияет): `untranslated_names` — нет имени/описания у способности или предмета (кроме `HIDDEN`), имени у юнита, `override_hero` героя, имени/описания у видимого Lua-модификатора (`LinkLuaModifier`; пропускаются `IsHidden() return true` и модификаторы `CreateModifierThinker`); `unknown_token_references` — `#токены` из Panorama (`text="#x"`, `$.Localize("#x")`) и Lua (`"#x_y"`), которых нет ни в одном языке; `missing_in_language` — ключи, которые есть в одном `addon_<lang>.txt`, но нет в другом; `bad_tooltip_variables` — `%name%` в `_Description`/`_Lore`/`_NoteN` способности, которого нет в её `AbilityValues`/`AbilitySpecial`.
9. `upsert_localization(addon_name: str, language: str, tokens: dict[str, str]) -> dict`
   - **Описание:** Добавляет или обновляет ключи локализации в `game/dota_addons/<addon_name>/resource/addon_<language>.txt` в кодировке `UTF-16` (по умолчанию, как в `addon_template`; кодировка существующего файла определяется по BOM и сохраняется) с соблюдением структуры `Tokens`. Переводы строк и `"` в значениях экранируются (`\n`, `\"`). В ответе: `missing_in_this_language` — ключи других языков, которых нет в этом файле; `not_yet_in_other_languages` — какие из записанных ключей ещё не переведены в другие языки.
   - **Факты движка (7.41):** `resource/addon_<lang>.txt` используется и для подсказок, и для `#токенов` Panorama (отдельный `panorama/localization/` не нужен; строка лога о его отсутствии — шум). Язык берётся из настроек при запуске Dota; `cl_language` во время игры его не меняет. Переменные подсказок: `%value%` из `AbilityValues`, `%%` — знак процента, в модификаторах `%dMODIFIER_PROPERTY_...%`.

### Модуль 4: Конструктор карт `.vmap` и Компилятор (`vmap_builder.py`)
10. `prepare_map_from_template(addon_name: str, map_name: str, source_template: str = "template_map") -> dict`
    - **Описание:** Копирует базовый `.vmap` из шаблона и переводит его через `dmxconvert.exe -oe keyvalues2 -of vmap` в текстовый формат, готовый к программному редактированию. Источник ищется в `content/dota_addons/<addon>/maps/`, `addon_template/maps/`, затем среди стоковых исходников `content/dota/maps/` (например `source_template="dota"` → `dota.vmap`, ~63 МБ бинарный → ~300 МБ текстовый); подмена на `template_map` — только если запрошен сам `template_map`. Для стоковой карты также создаёт `game/.../resource/overviews/<map>.txt` из стокового `resource/overviews/<source>.txt` (иначе миникарта серая); поле `minimap_overview` в ответе.
11. `list_map_entities(addon_name: str, map_name: str, classname_filter: str = "") -> dict`
    - **Описание:** Читает текстовый `.vmap` и возвращает компактный список всех сущностей (`CMapEntity`) на карте: их `id`, `nodeID`, `classname`, `targetname`, `origin` (координаты `x y z`), `angles` и ключевые свойства (без выгрузки полигональных мешей в контекст ИИ).
12. `add_map_entity(addon_name: str, map_name: str, classname: str, origin: str, targetname: str = "", angles: str = "0 0 0", scales: str = "1 1 1", properties: dict = None) -> dict`
    - **Описание:** Добавляет в `.vmap` новую точечную сущность (`info_player_start_goodguys`, `info_player_start_badguys`, `npc_dota_spawner`, `ent_dota_tree`, `prop_dynamic`, `info_target` и др.) с уникальными UUID всех вложенных блоков, `nodeID = max + 1` и регистрацией ссылок в `children` и `CVisibilityMgr` (`nodes` и `hiddenFlags`).
13. `remove_map_entity(addon_name: str, map_name: str, targetname_or_id: str) -> dict`
    - **Описание:** Удаляет точечную сущность из `.vmap` по её `targetname` или внутреннему `id` вместе со ссылками в `children` и `CVisibilityMgr`.
14. `compile_addon_resource(addon_name: str, resource_rel_path: str) -> dict`
    - **Описание:** Запускает `resourcecompiler.exe` для компиляции карты (`maps/<name>.vmap` с флагами `-fshallow -v -world -phys -gridnav -entities -nolightmaps`), Panorama UI (`panorama/layout/custom_game/...`), материалов или звуков. Для `.vsndevts` дополнительно компилирует каждый упомянутый `sounds/....vsnd` из исходника `.wav`/`.mp3` в `content/` (сам компилятор этого не делает) — поля `sound_sources_compiled`, `missing_sound_sources`. Возвращает статус сборки, список файлов в `maps/<map>.vpk` и отфильтрованный лог ошибок.

### Модуль 5: Управление игрой и живая отладка (`netcon_bridge.py`)
15. `run_console_command(command: str, wait_response_ms: int = 1200, verbose: bool = False) -> dict`
    - **Описание:** Отправляет консольную команду в запущенную Dota 2 по TCP (`127.0.0.1:2121`), например:
      - `dota_launch_custom_game <addon_name> <map_name>` — запуск карты.
      - `script_reload` — горячая перезагрузка Lua-скриптов без перезапуска карты.
      - `ent_find <substring>` — проверка сущностей на загруженной карте.
    - **Возвращает:** Ответ консоли и свежие строки лога (включая стектрейсы ошибок VScript/Lua). Известный шум движка (служебная информация сервера, Steam/GC, сетевые сообщения, отсутствующие стандартные ресурсы, дамп `script_help2`) скрывается и считается в `noise_lines_hidden`; метки времени убираются. `verbose=True` — сырой вывод.
16. `verify_vscript_api(search_term: str, refresh: bool = False, limit: int = 20) -> dict`
    - **Описание:** Ищет функции, классы и константы Lua в кэше `.cache/vscript_api/build_<ClientVersion>.txt`. Кэш строится один раз на билд Доты: команда `script_help2` (полный дамп ~12 000 строк), полный текст читается из `console.log` (NetCon обрезает вывод); дамп кэшируется, только если в нём ≥ 500 функций и есть ключевые классы (`CDOTAGameRules`, `CDOTABaseGameMode`, `CDOTA_BaseNPC`, `CDOTA_PlayerResource`). Дальше поиск работает без запущенной игры и не пишет в консоль. Если билд сменился, а игра не запущена, используется последний кэш (`source: stale_cache`). Ответ компактный: `сигнатура -- описание` для функций, строка `ИМЯ = число -- ...` для констант.
17. `read_latest_console_log(tail_lines: int = 40, grep: str = "", only_errors: bool = False, verbose: bool = False) -> dict`
    - **Описание:** Читает последний 1 МБ `game/dota/console.log` (при запуске Доты с `-condebug`), скрывает шум как `run_console_command`, `grep` оставляет строки с подстрокой, `only_errors` — только ошибки. Максимум 200 строк.
20. `take_game_screenshot(name: str = "mcp_shot", quality: int = 60) -> dict`
    - **Описание:** Делает снимок текущего кадра игры (мир + Panorama) командой движка `jpeg_screenshot <name> <quality>` через NetCon и возвращает абсолютный путь `game/dota/screenshots/<name>_NNNN.jpg` (`NNNN` растёт при повторе имени) и размер. Агент открывает `.jpg` средством чтения изображений и сам проверяет визуал (HUD, кат-сцены). Работает, когда окно Доты не в фокусе; нужна загруженная карта. Также есть `png_screenshot` и `screenshot` (проверено на 7.41).

### Модуль 6: Самодиагностика и Журнал багов (`diagnostics.py`)
18. `run_mcp_self_test() -> dict`
    - **Описание:** Проверяет готовность всей инфраструктуры на ПК: найден ли путь к Dota 2, открывается ли `pak01_dir.vpk`, доступны ли `dmxconvert.exe`, `resourcecompiler.exe`, `Source2Viewer-CLI.exe` и открыт ли порт `2121` (`netcon_port_open`).
19. `log_bug_report(component: str, symptom: str, root_cause: str, fix_applied: str, prevention_rule: str) -> dict`
    - **Описание:** Автоматически добавляет структурированную запись об обнаруженном и исправленном баге в `docs/BUG_LOG.md`.

---

## 5. Требования к запуску на Windows (Важные инварианты среды)

1. **Параметры запуска Dota 2 в Steam:**
   ```text
   -netconport 2121 -console -condebug
   ```
   *(Флаг `-tools` в параметры запуска Steam добавлять не нужно — режим **Launch Dota 2 - Tools** выбирается в диалоговом окне Steam при старте).*
2. **Запуск без прав администратора (`RUNASADMIN` запрещен):**
   - `dota2.exe`, `dota2cfg.exe` и `Antigravity.exe` должны работать с обычными правами пользователя (без галочки «Запускать от имени администратора» в свойствах совместимости). Наличие `~ RUNASADMIN` на `dota2.exe` блокирует запуск игры из окна Workshop Tools (`dota2cfg.exe`) с ошибкой `ERROR_ELEVATION_REQUIRED` (`WinError 740`).

---

## 6. Жизненный цикл создания кастомки агентом (Стандарт работы)

При получении задачи от пользователя («Сделай кастомку...») агент обязан выполнять шаги строго в следующем порядке:
1. **Инициализация:** Проверить/создать аддон через `create_or_configure_addon` и подготовить текстовую карту через `prepare_map_from_template`.
2. **Подбор ассетов (Без галлюцинаций):** Перед использованием любой модели, партикла, звука или базового скилла найти их точные пути через `search_dota_assets`, `search_sound_events` и `get_base_dota_definition`, а при необходимости проверить точки крепления и анимации через `inspect_model` / `inspect_particle`.
3. **Сборка карты (`.vmap`):** Проверить существующие объекты на карте через `list_map_entities`, добавить необходимые точки спавна, маркеры и декорации через `add_map_entity` и скомпилировать карту через `compile_addon_resource`.
4. **Написание данных и кода:** Создать/обновить KV-файлы (`npc_units_custom.txt`, `npc_abilities_custom.txt`, `npc_heroes_custom.txt`, `npc_items_custom.txt`), Lua-скрипты (`addon_game_mode.lua` и модули), Panorama UI и локализацию (`upsert_localization`).
5. **Валидация и Precache:** Запустить `validate_and_sync_precache` для проверки синтаксиса KV, существования всех путей ассетов и авто-генерации блока `Precache`. При наличии Panorama UI — скомпилировать его через `compile_addon_resource`.
6. **Запуск и самопроверка:** Запустить карту через `run_console_command("dota_launch_custom_game ...")`, считать логи консоли и при наличии ошибок Lua/KV автоматически исправить их и выполнить `script_reload`.
