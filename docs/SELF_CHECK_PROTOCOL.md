# Протокол инженерной самопроверки агента (`SELF_CHECK_PROTOCOL.md`)

Данный документ является обязательным чеклистом, по которому ИИ-агент проверяет свои действия перед созданием или модификацией кода MCP-сервера и кастомных игр Dota 2.

---

## 1. Самопроверка перед работой с ассетами (Модели, Партиклы, Звуки, Иконки)

- **Вопрос 1: Откуда взят путь к файлу (`.vmdl`, `.vpcf`, `.vsndevts`, `.vmat`)?**
  - *Запрещено:* Брать путь «по памяти» (например, угадывать `models/heroes/pudge/pudge_hook.vmdl`).
  - *Обязательно:* Вызвать `search_dota_assets(query)` и убедиться, что файл реально существует в `pak01_dir.vpk` или папке аддона.
- **Вопрос 2: Нет ли суффикса `_c` в путях внутри кода?**
  - *Проверка:* В `pak01_dir.vpk` файлы хранятся как `.vmdl_c`, `.vpcf_c`, `.vsnd_c`. В KV-файлах, Lua-скриптах и `.vmap` всегда используется исходное расширение без `_c` (`.vmdl`, `.vpcf`, `.vsndevts`).
- **Вопрос 3: Проверены ли точки крепления (`attach_*`) и анимации (`ACT_DOTA_*`) у модели?**
  - *Проверка:* Перед привязкой эффекта (`PATTACH_POINT_FOLLOW`) или назначением `Animation` в KV/Lua вызвать `inspect_model(model_path)` и убедиться, что `attach_hitloc` / `attach_attack1` и нужная `Activity` существуют у этой конкретной модели.
- **Вопрос 4: Известны ли `Control Points` (`CP`) у выбранного партикла?**
  - *Проверка:* Перед вызовом `ParticleManager:SetParticleControl(fx, cp, vec)` вызвать `inspect_particle(particle_path)`, чтобы точно знать, какие `CP` отвечают за старт, цель, радиус или скорость.

---

## 2. Самопроверка при написании Valve KeyValues (`.txt` / `.kv`) и Иконок (`spellicons` / `items`)

- **Вопрос 1: Актуален ли формат параметров способностей для Dota 2 (7.41+ / 2026)?**
  - *Проверка:* Блок `AbilitySpecial` устарел. Для новых способностей (`ability_lua` и `ability_datadriven`) использовать актуальный блок `AbilityValues` (или точно следовать структуре базовой способности из `get_base_dota_definition`, который автоматически сканирует и `npc_abilities.txt`, и `scripts/npc/heroes/npc_dota_hero_*.txt`).
  - *Проверка героев (7.41+):* Учитывать наличие врожденных способностей (`Innate`) и 4-го атрибута (`DOTA_ATTRIBUTE_ALL`).
- **Вопрос 2: Куда положены кастомные иконки скиллов и предметов (`.png`) и файлы Panorama?**
  - *Категорически запрещено:* Использовать устаревшую папку Source 1 `game/.../resource/flash3/images/` или класть сырые `.png`, `.xml`, `.css`, `.js` в `game/`.
  - *Обязательно:*
    - Иконки способностей класть в `content/dota_addons/<addon>/panorama/images/spellicons/<name>.png` и компилировать в `.vtex_c` (вызовом `validate_and_sync_precache` или `compile_addon_resource`).
    - Иконки предметов класть в `content/dota_addons/<addon>/panorama/images/items/<name>.png`, а в `npc_items_custom.txt` указывать `"AbilityTextureName" "item_<name>"` (с обязательным префиксом `item_`).
    - Всегда проверять маршрутизацию папок через инструмент `get_addon_paths(addon_name)`.
- **Вопрос 3: Совпадает ли `BaseClass` с типом сущности?**
  - *Проверка:*
    - Кастомный скилл на Lua -> `"BaseClass" "ability_lua"` + обязательный `"ScriptFile"`.
    - Кастомный юнит -> `"BaseClass" "npc_dota_creature"` (или `npc_dota_building`).
    - Кастомный предмет на Lua -> `"BaseClass" "item_lua"` + `"ScriptFile"`.
- **Вопрос 4: Валиден ли синтаксис KV и добавлен ли `Precache`?**
  - *Обязательно:* После любого изменения файлов в `scripts/npc/`, `scripts/vscripts/` или `panorama/images/` запускать инструмент `validate_and_sync_precache(addon_name)`.

---

## 3. Самопроверка при написании Lua VScripts (`scripts/vscripts/`)

- **Вопрос 0: Существует ли вызываемая функция Lua в актуальном движке Dota 2 7.41+?**
  - *Проверка:* При малейшем сомнении в точном названии метода `CDOTA_BaseNPC`, `CDOTABaseAbility`, `GameRules` или константы `MODIFIER_PROPERTY_*` вызвать инструмент `verify_vscript_api(search_term)` (обращается напрямую к `script_help2` запущенного движка Доты).

- **Вопрос 1: Разделен ли серверный и клиентский контекст (`IsServer()`)?**
  - *Проверка:* В модификаторах (`CDOTA_Modifier_Lua`) методы `OnCreated`, `OnIntervalThink`, `OnDestroy` вызываются и на клиенте, и на сервере. Все изменения состояния игры (`ApplyDamage`, `AddNewModifier`, `CreateUnitByName`, манипуляции со здоровьем/золотом) обязаны находиться внутри блока `if IsServer() then ... end`.
- **Вопрос 2: Зарегистрированы ли все модификаторы через `LinkLuaModifier`?**
  - *Проверка:* Каждый `modifier_*` обязан быть подключен через `LinkLuaModifier("modifier_name", "path/to/file", LUA_MODIFIER_MOTION_NONE)` с проверкой, что физический файл по этому пути существует.
- **Вопрос 3: Уничтожаются ли партиклы (`ParticleManager:ReleaseParticleIndex` / `DestroyParticle`)?**
  - *Проверка:* Для предотвращения утечек памяти и падения FPS все разовые партиклы освобождать через `ParticleManager:ReleaseParticleIndex(fx)`, а бесконечные (в баффах) — привязывать через `self:AddParticle(...)` в `OnCreated` модификатора.

---

## 4. Самопроверка при работе с картой (`.vmap`)

- **Вопрос 1: Не пытается ли агент прочитать `.vmap` через стандартный `read_file`?**
  - *Запрещено:* Читать `.vmap` напрямую (риск переполнения контекста мешами).
  - *Обязательно:* Использовать только `prepare_map_from_template`, `list_map_entities`, `add_map_entity`, `remove_map_entity`.
- **Вопрос 2: Клонируется ли реальная структура `CMapEntity` текущей версии Source 2?**
  - *Проверка:* Формат `keyvalues2` в `.vmap` чувствителен к типам атрибутов (`elementid`, `vector3`, `qangle`, `EditGameClassProps`). Добавление новых сущностей в `vmap_builder.py` должно клонировать эталонный шаблон узла `CMapEntity` из самой карты, чтобы на 100% совпадать с версией `dmxconvert.exe`.
- **Вопрос 3: Скомпилирована ли карта после правок?**
  - *Обязательно:* Вызвать `compile_addon_resource(addon_name, "maps/<map_name>.vmap")` и проверить код возврата `resourcecompiler.exe`.

---

## 5. Протокол фиксации багов и самообучения (`docs/BUG_LOG.md`)

1. Если во время работы на Windows любой инструмент MCP вернул ошибку, или в консоли Dota 2 (`run_console_command`) обнаружена ошибка компиляции/Lua/KV:
   - Агент обязан **немедленно записать инцидент** через инструмент `log_bug_report` (или напрямую в `docs/BUG_LOG.md`).
   - Формат записи: Дата/время, Компонент (MCP / VMap / Lua / KV / Panorama), Симптом/Текст ошибки, Корневая причина, Примененное решение, Правило предотвращения.
2. Перед стартом любой новой задачи агент сверяется с `docs/BUG_LOG.md`, чтобы не повторять ранее исправленные ошибки.
