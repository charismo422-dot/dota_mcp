# `dota_mcp` — Dota 2 Workshop Tools MCP Server для Antigravity

Автономный MCP-сервер для создания, редактирования карт (`.vmap`), подбора реальных ассетов из `pak01_dir.vpk`, компиляции ресурсов и отладки кастомных игр Dota 2 через ИИ-агента Antigravity.

---

## Быстрый старт на Windows-ПК с Dota 2

1. Склонируйте этот репозиторий и откройте папку проекта в **Antigravity** на вашем Windows-ПК:
   ```bash
   git clone https://github.com/charismo422-dot/dota_mcp.git
   ```
2. Напишите агенту в чате одну фразу:
   > **«Настрой проект и подключи MCP-сервер для Dota 2»**
3. Агент автоматически прочитает [GEMINI.md](./GEMINI.md) и [docs/TECHNICAL_SPEC.md](./docs/TECHNICAL_SPEC.md), сам создаст `.venv`, установит библиотеки, скачает `Decompiler.exe`, пропишет сервер в `mcp_config.json` и запустит самодиагностику `run_mcp_self_test()`.
4. Для живого управления игрой и чтения ошибок Lua запускайте Dota 2 Workshop Tools с параметрами запуска Steam:
   ```text
   -tools -netconport 29000 -console -condebug
   ```

---

## Документация проекта
- [Полная техническая спецификация (`docs/TECHNICAL_SPEC.md`)](./docs/TECHNICAL_SPEC.md)
- [Протокол инженерной самопроверки (`docs/SELF_CHECK_PROTOCOL.md`)](./docs/SELF_CHECK_PROTOCOL.md)
- [Журнал багов и исправлений (`docs/BUG_LOG.md`)](./docs/BUG_LOG.md)
- [Навык разработки кастомок (`.agents/skills/dota2-custom-game-dev/SKILL.md`)](./.agents/skills/dota2-custom-game-dev/SKILL.md)
