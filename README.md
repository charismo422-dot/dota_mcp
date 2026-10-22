# `dota_mcp` — Dota 2 Workshop Tools MCP Server для Antigravity

Автономный MCP-сервер для создания, редактирования карт (`.vmap`), подбора реальных ассетов из `pak01_dir.vpk`, компиляции ресурсов и отладки кастомных игр Dota 2 через ИИ-агента Antigravity.

---

## Быстрый старт на Windows-ПК с Dota 2

1. Склонируйте этот репозиторий и откройте папку проекта в **Antigravity** на вашем Windows-ПК:
   ```bash
   git clone https://github.com/charismo422-dot/dota_mcp.git
   ```
2. Напишите агенту в чате одну фразу:
   > **«Прочитай GEMINI.md и CODE_REVIEW_TODO.md, выполни Фазу 0 (настройка, проверка на реальных файлах Доты и починка по чеклисту) и подключи MCP-сервер»**
3. Агент автоматически прочитает [GEMINI.md](./GEMINI.md) и [docs/CODE_REVIEW_TODO.md](./docs/CODE_REVIEW_TODO.md):
   - создаст `.venv`, установит библиотеки, скачает `Source2Viewer-CLI.exe`;
   - снимет реальный образец `.vmap` через `dmxconvert.exe` вашей установленной Dota 2;
   - исправит все пункты 🔴 1–4 и 🟠 5–11 из ревью и протестирует сборку реальным `resourcecompiler.exe`;
   - пропишет сервер в `mcp_config.json` и запустит `run_mcp_self_test()`.
4. Для живого управления игрой и чтения ошибок Lua (без конфликта с портом `29000` от `vconsole2`) запускайте Dota 2 Workshop Tools с параметрами запуска Steam:
   ```text
   -tools -netconport 2121 -console -condebug
   ```

---

## Документация проекта
- **[План обязательной починки и проверки на Windows (`docs/CODE_REVIEW_TODO.md`)](./docs/CODE_REVIEW_TODO.md)**
- [Полная техническая спецификация (`docs/TECHNICAL_SPEC.md`)](./docs/TECHNICAL_SPEC.md)
- [Протокол инженерной самопроверки (`docs/SELF_CHECK_PROTOCOL.md`)](./docs/SELF_CHECK_PROTOCOL.md)
- [Журнал багов и исправлений (`docs/BUG_LOG.md`)](./docs/BUG_LOG.md)
- [Навык разработки кастомок (`.agents/skills/dota2-custom-game-dev/SKILL.md`)](./.agents/skills/dota2-custom-game-dev/SKILL.md)
