# `dota_mcp` — Dota 2 Workshop Tools MCP Server для Antigravity

Автономный MCP-сервер (19 инструментов) для создания, редактирования карт (`.vmap`), подбора реальных ассетов и звуковых событий из `pak01_dir.vpk`, компиляции ресурсов и живой отладки кастомных игр Dota 2 через ИИ-агента Antigravity.

> **Статус проекта:** ✅ **Фаза 0 полностью пройдена и верифицирована на Windows-ПК с Dota 2 (7.41+).**
> Все 19 инструментов протестированы на реальных бинарниках `dmxconvert.exe`, `resourcecompiler.exe`, `Source2Viewer-CLI.exe` и живом подключении к движку Dota 2 по NetCon (порт `2121`). В `dota_addons/mcp_test` развернута рабочая песочница для тестов.

---

## Настройка запуска Dota 2 и важные требования среды

1. **Параметры запуска Dota 2 в Steam:**
   Для живого управления игрой и чтения логов/ошибок Lua по TCP-мосту NetCon укажите в свойствах Dota 2 в Steam (**Свойства -> Общие -> Параметры запуска**):
   ```text
   -netconport 2121 -console -condebug
   ```
   *(Не добавляйте `-tools` в параметры запуска Steam — выбирайте **Launch Dota 2 - Tools** в штатном окне Steam при старте игры. Порт `2121` используется вместо `29000`, чтобы не конфликтовать с бинарным протоколом `vconsole2.exe`).*

2. **Запрет флага `RUNASADMIN` (Запуск от имени администратора):**
   - Ни `dota2.exe`, ни `dota2cfg.exe`, ни **Antigravity** **не должны** запускаться от имени администратора (в Свойствах `.exe` -> Совместимость галочка *«Запускать эту программу от имени администратора»* должна быть снята).
   - Иначе не-админский лаунчер Workshop Tools (`dota2cfg.exe`) при нажатии *Launch Tools* получит от Windows ошибку `ERROR_ELEVATION_REQUIRED` (`WinError 740` / `Failed to launch`).

3. **Автоматический приёмочный тест:**
   Для проверки целостности парсера `.vmap`, `dmxconvert.exe`, `resourcecompiler.exe` и инспекторов ресурсов в любой момент можно запустить:
   ```powershell
   $env:PYTHONPATH="."; .\.venv\Scripts\python tests\verify_phase0_acceptance.py
   ```

---

## Документация проекта
- [Полная техническая спецификация (`docs/TECHNICAL_SPEC.md`)](./docs/TECHNICAL_SPEC.md)
- [Протокол инженерной самопроверки (`docs/SELF_CHECK_PROTOCOL.md`)](./docs/SELF_CHECK_PROTOCOL.md)
- [Журнал багов и исправлений (`docs/BUG_LOG.md`)](./docs/BUG_LOG.md)
- [Эталонные дампы реальных форматов Dota 2 (`docs/reference_samples/`)](./docs/reference_samples/)
- [План проверки и починки Фазы 0 (`docs/CODE_REVIEW_TODO.md`)](./docs/CODE_REVIEW_TODO.md)
- [Навык разработки кастомок (`.agents/skills/dota2-custom-game-dev/SKILL.md`)](./.agents/skills/dota2-custom-game-dev/SKILL.md)
