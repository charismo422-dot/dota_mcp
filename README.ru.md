# `dota_mcp` — MCP-сервер Dota 2 Workshop Tools

> **[English Documentation (README.md)](./README.md)**
>
> **Статус проекта:** `Alpha` — Основной функционал (19 инструментов MCP) полностью проверен на Windows 10/11 с Dota 2 (7.41+), реальными бинарниками `dmxconvert.exe`, `resourcecompiler.exe`, `Source2Viewer-CLI.exe` и живым TCP-мостом NetCon (`127.0.0.1:2121`).

`dota_mcp` — специализированный сервер **Model Context Protocol (MCP)** и набор правил/навыков для ИИ-агентов, позволяющий автономно создавать, редактировать карты (`.vmap`), находить реальные ассеты в `pak01_dir.vpk`, компилировать ресурсы и вживую отлаживать кастомные игры **Dota 2** на Windows без выдумывания путей и функций Lua API.

---

## Возможности (19 инструментов MCP)

1. **Поиск реальных ассетов и звуков без галлюцинаций (`pak01_dir.vpk`):**
   - `search_dota_assets`: Поиск моделей (`.vmdl`), партиклов (`.vpcf`), материалов (`.vmat`), иконок Panorama (`.vtex`) и скриптов в `pak01_dir.vpk`.
   - `search_sound_events`: Декомпиляция `.vsndevts_c` для извлечения точных имён звуковых событий (например, `Hero_Huskar.Inner_Fire.Cast`) и путей к звуковым файлам для `Precache`.
   - `get_base_dota_definition`: Чтение актуальных KV-определений героев, способностей, юнитов и предметов Dota 2 (7.41+), включая вложенные блоки `AbilityDefinitions` в файлах героев.
2. **Глубокая инспекция скомпилированных ресурсов (`Source2Viewer-CLI.exe`):**
   - `inspect_model`: Извлечение списка анимаций (`ACT_DOTA_*`), точек крепления (`attach_hitloc`, `attach_attack1`) и костей из `.vmdl_c`.
   - `inspect_particle`: Извлечение используемых `Control Points` (`CP0`..`CPn`), дочерних партиклов, инициализаторов и операторов из `.vpcf_c`.
3. **Безопасная работа с картами (`.vmap`) и компиляция:**
   - `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, `remove_map_entity`, `compile_addon_resource`: Конвертация `.vmap` через `dmxconvert.exe`, добавление и удаление точечных сущностей с уникальными UUID и синхронизацией `CVisibilityMgr` без переполнения контекста агента, а также компиляция карт в `.vpk` (`.vmap_c`, `.gnv`) через `resourcecompiler.exe`.
4. **Управление аддоном, локализация и авто-Precache:**
   - `create_or_configure_addon`, `get_addon_paths`, `upsert_localization` (`UTF-16`), `validate_and_sync_precache`: Проверка синтаксиса Valve KeyValues, поиск файлов в неправильных папках, авто-компиляция `.png` иконок в `.vtex_c` и генерация `auto_precache.lua`.
5. **Живая связь с запущенной Dota 2 (`NetCon` TCP порт `2121`):**
   - `run_console_command`, `verify_vscript_api` (`script_help2`), `read_latest_console_log`: Запуск кастомки из консоли, горячая перезагрузка скриптов (`script_reload`), проверка реальных функций Lua API в запущенном движке и чтение логов/ошибок.
6. **Самодиагностика и журнал багов:**
   - `run_mcp_self_test`, `log_bug_report`.

---

## Системные требования

- **ОС:** Windows 10 / 11 (64-bit) — *необходима для работы штатных утилит Source 2 `dmxconvert.exe` и `resourcecompiler.exe`*.
- **Dota 2 + DLC Workshop Tools:** Установлены через Steam (Библиотека Steam -> ПКМ по **Dota 2** -> **Свойства** -> **Доп. контент (DLC)** -> поставить галочку **Dota 2 Workshop Tools DLC**).
- **Python:** Версия `3.10` или новее (`python` и `pip` доступны в `PATH`).
- **Git:** Установлен и доступен в `PATH`.

---

## Быстрый старт

1. **Склонируйте репозиторий:**
   ```powershell
   git clone https://github.com/charismo422-dot/dota_mcp.git
   cd dota_mcp
   ```

2. **Запустите скрипт установки:**
   ```powershell
   python setup.py
   ```
   *(Или `.\setup.ps1` в PowerShell. Если Dota 2 установлена в нестандартную папку, укажите путь явно: `python setup.py --dota-path "D:\Path\To\dota 2 beta"`).*

   **Что автоматически делает `setup.py`:**
   - Создаёт виртуальное окружение `.venv` и ставит зависимости (`mcp>=2.3.0,<3.0.0`, `vpk`, `vdf`, `requests`).
   - Находит установленную Dota 2 и проверяет наличие утилит Workshop Tools (`dmxconvert.exe`, `resourcecompiler.exe`, `addon_template`).
   - Скачивает актуальный `Source2Viewer-CLI.exe` в папку `bin/`.
   - Бережно добавляет `dota2-workshop-mcp` в `mcp_config.json` для Antigravity (не затирая другие ваши MCP-серверы), генерирует `.mcp.json` в корне проекта и копирует навык в `.claude/skills/` для Claude Code.
   - Запускает самопроверку `run_mcp_self_test`.

3. **Перезапустите ИИ-агента**, чтобы он подхватил MCP-сервер `dota2-workshop-mcp` и правила проекта.

---

## Обязательные настройки запуска Dota 2 и права Windows

1. **Параметры запуска Dota 2 в Steam:**
   В свойствах Dota 2 в Steam (**Свойства -> Общие -> Параметры запуска**) укажите:
   ```text
   -netconport 2121 -console -condebug
   ```
   > **Важно:** Не добавляйте флаг `-tools` в параметры запуска Steam — выбирайте пункт **Launch Dota 2 - Tools** в стандартном диалоговом окне Steam при старте игры. Порт `2121` используется вместо `29000`, чтобы не конфликтовать с бинарным протоколом `vconsole2.exe`.

2. **Не запускайте Dota 2 и ИИ-агента от имени администратора (`RUNASADMIN`):**
   - Ни у `dota2.exe`, ни у `dota2cfg.exe`, ни у программы-агента (например, **Antigravity**) не должна стоять галочка *«Запускать эту программу от имени администратора»* в свойствах совместимости Windows, и их не следует запускать из админского терминала.
   - Если на `dota2.exe` стоит флаг `RUNASADMIN`, лаунчер Workshop Tools (`dota2cfg.exe`) не сможет запустить игру и выдаст ошибку `Failed to launch` (`WinError 740: ERROR_ELEVATION_REQUIRED`).

---

## Поддерживаемые ИИ-агенты

| Агент | Статус поддержки | Как подключаются правила и MCP |
| :--- | :--- | :--- |
| **Google Antigravity** | **Проверено в бою** | Читает `GEMINI.md` -> `@[AGENTS.md](./AGENTS.md)`, навык из `.agents/skills/dota2-custom-game-dev/` и конфиг из `~/.gemini/antigravity/mcp_config.json` (`~/.gemini/config/mcp_config.json`). |
| **Claude Code** | **Настроен (не проверен)** | Читает `CLAUDE.md` -> `@AGENTS.md`, навык из `.claude/skills/dota2-custom-game-dev/` и конфиг `.mcp.json` в корне проекта. |
| **Другие агенты (Cursor, Windsurf, Codex)** | **Совместимы через `AGENTS.md`** | Правила в `AGENTS.md`; в настройках MCP укажите запуск `.venv\Scripts\python.exe -m src.dota2_mcp.server`. |

---

## Рабочий пример (`examples/mcp_test`)

В папке [`examples/mcp_test/`](./examples/mcp_test/README.md) находятся исходники тестового аддона `mcp_test` с кастомной Lua-способностью **«Огненное кольцо» (`mcp_ring_of_fire`)**, авто-предзагрузкой ресурсов, русской и английской локализацией и спавном пассивных мишеней с авто-респавном.

Для запуска приёмочного автотеста парсера карт `.vmap`, `dmxconvert.exe` и `resourcecompiler.exe`:
```powershell
.\.venv\Scripts\python.exe tests\verify_phase0_acceptance.py
```

---

## Известные ограничения (Alpha)

- **Удаление сущностей в `.vmap`:** Инструмент `remove_map_entity` рассчитан на точечные сущности (`CMapEntity`). При удалении сложных брашевых сущностей со вложенными мешами вложенные элементы не обрабатываются.
- **Лимит буфера одиночной команды NetCon:** TCP-сокет NetCon в Dota 2 обрезает вывод одной команды примерно на 3 600 строках; инструмент `verify_vscript_api` автоматически дочитывает полный вывод `script_help2` (~12 000 строк) из `game/dota/console.log` (требуется флаг `-condebug`).
- **Только Windows:** Конвертация карт и компиляция ресурсов требуют бинарников Workshop Tools (`dmxconvert.exe`, `resourcecompiler.exe`), которые поставляются Valve только под Windows x64.

---

## Документация проекта

- [Единые правила для ИИ-агентов (`AGENTS.md`)](./AGENTS.md)
- [Полная техническая спецификация (`docs/TECHNICAL_SPEC.md`)](./docs/TECHNICAL_SPEC.md)
- [Протокол инженерной самопроверки (`docs/SELF_CHECK_PROTOCOL.md`)](./docs/SELF_CHECK_PROTOCOL.md)
- [Журнал багов и исправлений (`docs/BUG_LOG.md`)](./docs/BUG_LOG.md)
- [Эталонные дампы реальных форматов Dota 2 (`docs/reference_samples/`)](./docs/reference_samples/)
- [Архив чеклиста Фазы 0 (`docs/history/CODE_REVIEW_TODO.md`)](./docs/history/CODE_REVIEW_TODO.md)
