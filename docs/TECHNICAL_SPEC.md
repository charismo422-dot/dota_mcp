# Техническая спецификация проекта `dota_mcp` (Dota 2 Workshop Tools MCP Server)

## 1. Назначение системы
`dota_mcp` — специализированный сервер Model Context Protocol (MCP) и набор правил/навыков для ИИ-агента Antigravity, позволяющий создавать, модифицировать, компилировать и отлаживать кастомные игры (Custom Games) в **Dota 2 Workshop Tools** на ОС Windows полностью автономно по текстовому запросу пользователя.

---

## 2. Архитектура и технологический стек

### 2.1. Стек разработки кастомок (Target Stack)
- **Логика (VScripts):** Lua 5.1/5.2 (штатный движок Source 2 `game/dota_addons/<addon>/scripts/vscripts/`).
- **Данные (DataDriven / KV):** Valve KeyValues (`.txt` / `.kv` в `game/dota_addons/<addon>/scripts/npc/`).
- **Интерфейс (UI):** Panorama UI (`.xml`, `.css`, `.js` в `content/dota_addons/<addon>/panorama/`).
- **Карты (Maps):** Source 2 `.vmap` (редактирование в текстовом формате `keyvalues2` через штатный `dmxconvert.exe`, компиляция в `.vmap_c` через `resourcecompiler.exe`).
- **Локализация:** `game/dota_addons/<addon>/resource/addon_<language>.txt` (UTF-8 / UCS-2 LE).

### 2.2. Стек MCP-сервера (`dota2_mcp/`)
- **Язык:** Python 3.10+
- **Фреймворк MCP:** `mcp` (`FastMCP`, транспорт `stdio`)
- **Библиотеки Python:**
  - `vpk` (ValvePython) — чтение индекса и извлечение файлов из `game/dota/pak01_dir.vpk` без распаковки всего архива на диск.
  - `vdf` (ValvePython) — парсинг и сериализация файлов Valve KeyValues (`.txt`, `.kv`, `addoninfo.txt`).
- **Внешние бинарные утилиты Source 2 (входят в состав Dota 2 Workshop Tools):**
  - `<dota_path>/game/bin/win64/dmxconvert.exe` — конвертация карт `.vmap` между бинарным форматом и текстовым `keyvalues2`.
  - `<dota_path>/game/bin/win64/resourcecompiler.exe` — компиляция `.vmap`, Panorama UI, звуков и материалов в скомпилированные ассеты (`_c`).
- **Внешний CLI-инспектор скомпилированных ресурсов (`_c`):**
  - `Decompiler.exe` (Source 2 Viewer CLI / `ValveResourceFormat`) — автоматическое скачивание в `bin/Decompiler.exe` при установке на Windows. Используется для чтения анимаций и точек крепления (`Attachment points`) из `.vmdl_c`, а также Control Points из `.vpcf_c`.
- **Сетевой интерфейс движка (Live Engine Bridge):**
  - TCP-клиент к порту `-netconport 2121` (текстовый Telnet-поток запущенной Dota 2, не конфликтующий с портом `29000` бинарного `vconsole2.exe`) для отправки команд (`dota_launch_custom_game`, `script_reload`, `ent_create`) и чтения логов/ошибок Lua в реальном времени.

---

## 3. Структура репозитория `dota_mcp`

```text
dota_mcp/
├── GEMINI.md                                  # Главные правила проекта и авто-инструкции агента
├── README.md                                  # Инструкция по развертыванию агентом на Windows
├── requirements.txt                           # Python-зависимости (mcp, vpk, vdf, requests)
├── docs/
│   ├── TECHNICAL_SPEC.md                      # Полная техническая спецификация (этот документ)
│   ├── SELF_CHECK_PROTOCOL.md                 # Протокол инженерной самопроверки агента
│   └── BUG_LOG.md                             # Журнал фиксации багов, ошибок и исправлений
├── .agents/
│   └── skills/
│       └── dota2-custom-game-dev/
│           └── SKILL.md                       # Пошаговый алгоритм для агента по созданию кастомок
└── src/
    └── dota2_mcp/
        ├── __init__.py
        ├── server.py                          # Точка входа FastMCP и регистрация всех инструментов
        ├── config.py                          # Автоопределение путей Steam, Dota 2, dmxconvert, resourcecompiler
        ├── vpk_explorer.py                    # Модуль 1: Поиск ассетов и чтение базовых KV в pak01_dir.vpk
        ├── asset_inspector.py                 # Модуль 2: Инспекция .vmdl_c (анимации/attachments) и .vpcf_c (CP)
        ├── addon_manager.py                   # Модуль 3: Создание аддона, валидация KV, авто-Precache, локализация
        ├── vmap_builder.py                    # Модуль 4: Чтение/модификация .vmap через dmxconvert + компиляция
        ├── netcon_bridge.py                   # Модуль 5: TCP-мост к запущенной Dota 2 (-netconport)
        └── diagnostics.py                     # Модуль 6: Самодиагностика MCP и авто-логирование багов в BUG_LOG.md
```

---

## 4. Спецификация инструментов MCP-сервера (Tools Reference)

### Модуль 1: Поиск ассетов и оригинальных скриптов (`vpk_explorer.py`)
1. `search_dota_assets(query: str, asset_type: str = "all", limit: int = 25) -> dict`
   - **Описание:** Ищет в `game/dota/pak01_dir.vpk` реальные пути к файлам по подстроке/ключевым словам.
   - **Фильтры `asset_type`:** `"model"` (`.vmdl`), `"particle"` (`.vpcf`), `"sound"` (`.vsnd` / `.vsndevts`), `"material"` (`.vmat`), `"panorama"` (`.png` / `.vsvg`), `"script"` (`.txt` / `.lua`), `"all"`.
   - **Особенность:** Автоматически убирает суффикс `_c` у возвращаемых путей, чтобы пути сразу подходили для вставки в Lua, KV и `.vmap`.
2. `search_sound_events(query: str, file_filter: str = "", limit: int = 30) -> dict`
   - **Описание:** Ищет внутри `soundevents/**/*.vsndevts_c` в `pak01_dir.vpk` (через `Source2Viewer-CLI.exe -b DATA` или поиск строк) точные имена звуковых событий (например, `Hero_Pudge.Attack`) для использования в `EmitSoundOn` / `StopSoundOn`, а также возвращает путь к файлу `.vsndevts` для предзагрузки (`PrecacheResource("soundfile", ...)`).
3. `get_base_dota_definition(category: str, name: str) -> dict`
   - **Описание:** Извлекает из `pak01_dir.vpk` (`scripts/npc/npc_heroes.txt`, `npc_abilities.txt`, `scripts/npc/heroes/npc_dota_hero_*.txt`, `npc_units.txt`, `items.txt`) точный блок настроек стандартного героя, способности, юнита или предмета актуальной Dota 2 (7.41+).
   - **Параметр `category`:** `"hero"`, `"ability"`, `"unit"`, `"item"`.

### Модуль 2: Глубокая инспекция моделей и партиклов (`asset_inspector.py`)
3. `inspect_model(model_path: str) -> dict`
   - **Описание:** Извлекает `.vmdl_c` из VPK (или папки аддона), декомпилирует через `Decompiler.exe` и возвращает список:
     - `animations`: имена анимаций и связанные `Activity` (например, `ACT_DOTA_ATTACK`, `ACT_DOTA_DIE`, `ACT_DOTA_CAST_ABILITY_1`).
     - `attachments`: точки крепления эффектов/оружия (например, `attach_hitloc`, `attach_attack1`).
4. `inspect_particle(particle_path: str) -> dict`
   - **Описание:** Декомпилирует `.vpcf_c` и возвращает список используемых `Control Points` (`CP0`, `CP1` и т.д.), их типы (вектор позиции, радиус, цвет, ориентация) и дочерние эффекты.

### Модуль 3: Управление аддоном, KV, Precache и локализацией (`addon_manager.py`)
5. `create_or_configure_addon(addon_name: str, maps: list[str], max_players: int = 10, team_count: int = 2) -> dict`
   - **Описание:** Создает структуру нового аддона в `content/dota_addons/<addon_name>` и `game/dota_addons/<addon_name>` на базе штатного `addon_template` (если аддон еще не создан), настраивает `addoninfo.txt` и возвращает таблицу маршрутизации папок.
6. `get_addon_paths(addon_name: str) -> dict`
   - **Описание:** Возвращает точные канонические пути для `game/` (исполняемые файлы Lua, KV, локализация) и `content/` (исходники `.vmap`, Panorama `.xml`/`.css`/`.js`, кастомные иконки `.png` в `spellicons/` и `items/`).
7. `validate_and_sync_precache(addon_name: str) -> dict`
   - **Описание:**
     1. Проверяет все `.txt` / `.kv` файлы в `game/dota_addons/<addon_name>/scripts/npc/` через парсер `vdf` на синтаксические ошибки и правильность префиксов `AbilityTextureName` (`item_` для предметов).
     2. Ловит ошибочно размещенные файлы (например, устаревшую папку `resource/flash3`, сырые `.png`/`.xml`/`.css`/`.js` в `game/` или `.lua` в `content/`).
     3. Автоматически компилирует новые `.png` иконки из `content/.../panorama/images/` в `.vtex_c` через `resourcecompiler.exe`.
     4. Сканирует все `.lua` и `.txt` файлы аддона на наличие путей `.vmdl`, `.vpcf`, `.vsndevts` и проверяет их существование в `pak01_dir.vpk`.
     5. Автоматически формирует/обновляет список `PrecacheResource` в `auto_precache.lua` и подключает его к `addon_game_mode.lua`.
8. `upsert_localization(addon_name: str, language: str, tokens: dict[str, str]) -> dict`
   - **Описание:** Добавляет или обновляет ключи локализации (названия скиллов, описания, модификаторы, UI-тексты) в `game/dota_addons/<addon_name>/resource/addon_<language>.txt` с соблюдением структуры `Tokens`.

### Модуль 4: Конструктор карт `.vmap` и Компилятор (`vmap_builder.py`)
9. `prepare_map_from_template(addon_name: str, map_name: str, source_template: str = "template_map") -> dict`
   - **Описание:** Копирует базовый `.vmap` из шаблона и переводит его через `dmxconvert.exe -oe keyvalues2 -of vmap` в текстовый формат, готовый к программному редактированию.
10. `list_map_entities(addon_name: str, map_name: str, classname_filter: str = "") -> dict`
    - **Описание:** Читает текстовый `.vmap` и возвращает компактный список всех сущностей (`CMapEntity`) на карте: их `id`, `classname`, `targetname`, `origin` (координаты `x y z`), `angles` и ключевые свойства (без выгрузки гигабайтных полигональных мешей в контекст ИИ).
11. `add_map_entity(addon_name: str, map_name: str, classname: str, origin: str, targetname: str = "", angles: str = "0 0 0", scales: str = "1 1 1", properties: dict = None) -> dict`
    - **Описание:** Добавляет в `.vmap` новую сущность (`info_player_start_goodguys`, `info_player_start_badguys`, `npc_dota_spawner`, `ent_dota_tree`, `prop_dynamic`, `info_target`, `trigger_multiple` и др.) с валидным UUID и структурой `CMapEntity` в формате KeyValues2.
12. `remove_map_entity(addon_name: str, map_name: str, targetname_or_id: str) -> dict`
    - **Описание:** Удаляет сущность из `.vmap` по её `targetname` или внутреннему `id`.
13. `compile_addon_resource(addon_name: str, resource_rel_path: str) -> dict`
    - **Описание:** Запускает `resourcecompiler.exe -i "<content_path>/<resource_rel_path>" -v` для компиляции карты (`maps/<name>.vmap`), Panorama UI (`panorama/layout/custom_game/...`), материалов или звуков. Возвращает статус сборки и отфильтрованный лог ошибок.

### Модуль 5: Управление игрой и живая отладка (`netcon_bridge.py`)
14. `run_console_command(command: str, wait_response_ms: int = 1200) -> dict`
    - **Описание:** Отправляет консольную команду в запущенную Dota 2 по TCP (`127.0.0.1:2121`), например:
      - `dota_launch_custom_game <addon_name> <map_name>` — запуск карты.
      - `script_reload` — горячая перезагрузка Lua-скриптов без перезапуска карты.
      - `dota_dev forcegamestart` — принудительный старт игры.
    - **Возвращает:** Ответ консоли и свежие строки лога (включая стектрейсы ошибок VScript/Lua).
15. `verify_vscript_api(search_term: str) -> dict`
    - **Описание:** Запрашивает у живого движка Dota 2 (7.41+) через `script_help2 <search_term>` реальные сигнатуры функций Lua и константы модификаторов.
16. `read_latest_console_log(tail_lines: int = 80) -> dict`
    - **Описание:** Читает последние строки и ошибки из `game/dota/console.log` на диске (резервный канал, если Дота запущена с `-condebug`).

### Модуль 6: Самодиагностика и Журнал багов (`diagnostics.py`)
17. `run_mcp_self_test() -> dict`
    - **Описание:** Проверяет готовность всей инфраструктуры на ПК: найден ли путь к Dota 2, открывается ли `pak01_dir.vpk`, доступны ли `dmxconvert.exe`, `resourcecompiler.exe`, `Decompiler.exe` (если нет — автоматически скачивает последний релиз `cli-windows-x64.zip` из `ValveResourceFormat`), и слушает ли Dota 2 порт `netconport`.
18. `log_bug_report(component: str, symptom: str, root_cause: str, fix_applied: str, prevention_rule: str) -> dict`
    - **Описание:** Автоматически добавляет структурированную запись об обнаруженном и исправленном баге в `docs/BUG_LOG.md`.

---

## 5. Развертывание на Windows-ПК силами агента (Zero-Script Bootstrap)

Когда пользователь открывает склонированный репозиторий в Antigravity на Windows-ПК с установленной Dota 2 и пишет: *«Настрой проект и подключи MCP»*, агент выполняет следующие шаги:
1. Создает виртуальное окружение: `python -m venv .venv` и устанавливает зависимости: `.venv\Scripts\pip install -r requirements.txt`.
2. Запускает первичную проверку и автозагрузку `Decompiler.exe`: `.venv\Scripts\python -m src.dota2_mcp.diagnostics --bootstrap`.
3. Прописывает MCP-сервер в глобальный конфиг Antigravity (`~/.gemini/config/mcp_config.json`):
   ```json
   {
     "mcpServers": {
       "dota2-workshop-mcp": {
         "command": "<АБСОЛЮТНЫЙ_ПУТЬ_К_РЕПО>/.venv/Scripts/python.exe",
         "args": ["-m", "src.dota2_mcp.server"],
         "env": {
           "PYTHONPATH": "<АБСОЛЮТНЫЙ_ПУТЬ_К_РЕПО>"
         }
       }
     }
   }
   ```
4. Вызывает `run_mcp_self_test()` для подтверждения полной готовности.

---

## 6. Жизненный цикл создания кастомки агентом (Стандарт работы)

При получении задачи от пользователя («Сделай кастомку...») агент обязан выполнять шаги строго в следующем порядке:
1. **Инициализация:** Проверить/создать аддон через `create_or_configure_addon` и подготовить текстовую карту через `prepare_map_from_template`.
2. **Подбор ассетов (Без галлюцинаций):** Перед использованием любой модели, партикла, звука или базового скилла найти их точные пути через `search_dota_assets` и `get_base_dota_definition`, а при необходимости проверить точки крепления и анимации через `inspect_model` / `inspect_particle`.
3. **Сборка карты (`.vmap`):** Проверить существующие объекты на карте через `list_map_entities`, добавить необходимые точки спавна, триггеры, декорации и объекты через `add_map_entity` и скомпилировать карту через `compile_addon_resource`.
4. **Написание данных и кода:** Создать/обновить KV-файлы (`npc_units_custom.txt`, `npc_abilities_custom.txt`, `npc_heroes_custom.txt`, `npc_items_custom.txt`), Lua-скрипты (`addon_game_mode.lua` и модули), Panorama UI и локализацию (`upsert_localization`).
5. **Валидация и Precache:** Запустить `validate_and_sync_precache` для проверки синтаксиса KV, существования всех путей ассетов и авто-генерации блока `Precache`. При наличии Panorama UI — скомпилировать его через `compile_addon_resource`.
6. **Запуск и самопроверка:** Запустить карту через `run_console_command("dota_launch_custom_game ...")`, считать логи консоли и при наличии ошибок Lua/KV автоматически исправить их и выполнить `script_reload`.
