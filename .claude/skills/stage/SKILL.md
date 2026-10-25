---
name: stage
description: Start one stage of the plan in a fresh session (owner-invoked).
disable-model-invocation: true
argument-hint: "[результат проверки или описание этапа]"
---

# /stage — один этап за сессию

Аргументы владельца: $ARGUMENTS

1. Возьми раздел «## Следующий шаг» из `.private/STATUS.md` — он уже подставлен хуком в начале сессии; файл заново не читай, если раздел виден в контексте.
2. Разбери `$ARGUMENTS`:
   - **результат проверки владельца** (что увидел/услышал по прошлому этапу) — запиши в `.private/STATUS.md`; найденные ошибки — в `docs/BUG_LOG.md` (`log_bug_report`);
   - **описание нового этапа** — сначала добавь его в `docs/TEST_PLAN.md` со статусом todo, потом выполняй.
3. Выполни **ОДИН** этап по правилам `AGENTS.md` §4 (минимум, PASS один раз, ≤ 3 скриншота, только RU, логи через grep/tail).
4. В конце вызови `/wrap`. Следующий этап не начинай.
