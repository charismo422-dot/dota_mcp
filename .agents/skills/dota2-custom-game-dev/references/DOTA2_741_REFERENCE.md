# Dota 2 (Patch 7.41+ / 2026) Architecture, Paths & Boilerplate Reference

## 1. Strict `game/` vs `content/` Separation Table

| File Type | Where Agent Writes Source | Needs `resourcecompiler.exe`? | Final Runtime Location in `game/` |
| :--- | :--- | :--- | :--- |
| **Lua VScripts (`.lua`)** | `game/dota_addons/<addon>/scripts/vscripts/` | **NO** | Same (`game/.../scripts/vscripts/`) |
| **NPC KeyValues (`.txt`/`.kv`)** | `game/dota_addons/<addon>/scripts/npc/` | **NO** | Same (`game/.../scripts/npc/`) |
| **Localization (`addon_*.txt`)** | `game/dota_addons/<addon>/resource/` | **NO** | Same (`game/.../resource/`) |
| **Maps (`.vmap`)** | `content/dota_addons/<addon>/maps/<map>.vmap` | **YES** | `game/dota_addons/<addon>/maps/<map>.vmap_c` |
| **Custom Ability Icons (`.png`)** | `content/dota_addons/<addon>/panorama/images/spellicons/<name>.png` | **YES** (auto-compiled by `validate_and_sync_precache`) | `game/.../panorama/images/spellicons/<name>_png.vtex_c` |
| **Custom Item Icons (`.png`)** | `content/dota_addons/<addon>/panorama/images/items/<name>.png` | **YES** (auto-compiled by `validate_and_sync_precache`) | `game/.../panorama/images/items/<name>_png.vtex_c` |
| **Panorama Layout (`.xml`)** | `content/dota_addons/<addon>/panorama/layout/custom_game/` | **YES** | `game/.../panorama/layout/custom_game/*.vxml_c` |
| **Panorama Styles (`.css`)** | `content/dota_addons/<addon>/panorama/styles/custom_game/` | **YES** | `game/.../panorama/styles/custom_game/*.vcss_c` |
| **Panorama Scripts (`.js`)** | `content/dota_addons/<addon>/panorama/scripts/custom_game/` | **YES** | `game/.../panorama/scripts/custom_game/*.vjs_c` |
| **Custom Sound Events (`.vsndevts`)** | `content/dota_addons/<addon>/soundevents/` | **YES** | `game/.../soundevents/*.vsndevts_c` |

> **CRITICAL BAN:** NEVER create or use `game/dota_addons/<addon>/resource/flash3/`! That was Source 1 / Scaleform and is completely dead in Dota 2 7.41+.

---

## 2. Custom Ability & Item Icons Rules (`AbilityTextureName`)

1. **Reusing a built-in Dota 2 icon:**
   - Ability: `"AbilityTextureName" "pudge_meat_hook"` (or whatever the original ability name is in `get_base_dota_definition`).
   - Item: `"AbilityTextureName" "item_blink"`.
2. **Using a Custom Ability Icon (`.png`):**
   - Put file at: `content/dota_addons/<addon>/panorama/images/spellicons/my_fireball.png` (128x128 PNG).
   - In `npc_abilities_custom.txt`: `"AbilityTextureName" "my_fireball"`.
   - Run `validate_and_sync_precache(addon_name)` (or `compile_addon_resource`) so `my_fireball_png.vtex_c` is generated in `game/`.
3. **Using a Custom Item Icon (`.png`):**
   - Put file at: `content/dota_addons/<addon>/panorama/images/items/excalibur.png` (88x64 PNG).
   - In `npc_items_custom.txt`: **`"AbilityTextureName" "item_excalibur"`** (MUST include the `item_` prefix in KV, while the `.png` filename inside `panorama/images/items/` does NOT have `item_`!).

---

## 3. Patch 7.41+ KeyValues Standards (`AbilityValues`, Innates, Universal Heroes)

### 3.1. `npc_abilities_custom.txt` (Use `AbilityValues`, NOT `AbilitySpecial`)
```kv
"DOTAAbilities"
{
    "Version"   "1"

    "custom_fire_nova"
    {
        "BaseClass"                 "ability_lua"
        "ScriptFile"                "abilities/custom_fire_nova.lua"
        "AbilityTextureName"        "lina_light_strike_array"
        "AbilityBehavior"           "DOTA_ABILITY_BEHAVIOR_NO_TARGET | DOTA_ABILITY_BEHAVIOR_IMMEDIATE"
        "AbilityUnitDamageType"     "DAMAGE_TYPE_MAGICAL"
        "MaxLevel"                  "4"
        "AbilityCooldown"           "8.0 7.0 6.0 5.0"
        "AbilityManaCost"           "60 70 80 90"

        "AbilityValues"
        {
            "radius"
            {
                "value"                     "400"
                "affected_by_aoe_increase"  "1"
            }
            "damage"                        "120 200 280 360"
            "stun_duration"                 "1.5"
        }
    }
}
```

### 3.2. `npc_heroes_custom.txt` (Handling 7.41+ Innates & Ability Slots)
When overriding a hero in 7.41+, remember that standard heroes have Innate abilities and up to 24 ability slots (`Ability1`..`Ability24`).
- To replace a hero's main kit cleanly without breaking their HUD layout, either inspect their base definition first via `get_base_dota_definition("hero", "npc_dota_hero_...")` or explicitly set `Ability1`..`Ability6`.
- Note `DOTA_ATTRIBUTE_ALL` is a valid `AttributePrimary` for Universal heroes alongside `DOTA_ATTRIBUTE_STRENGTH`, `DOTA_ATTRIBUTE_AGILITY`, `DOTA_ATTRIBUTE_INTELLECT`.

---

## 4. Standard `addon_game_mode.lua` Boilerplate (Fast Start, No 90s Draft Wait)

```lua
if CCustomGameMode == nil then
    CCustomGameMode = class({})
end

function Precache(context)
    pcall(function() require("auto_precache")(context) end)
end

function Activate()
    GameRules.Addon = CCustomGameMode()
    GameRules.Addon:InitGameMode()
end

function CCustomGameMode:InitGameMode()
    local GameMode = GameRules:GetGameModeEntity()

    -- Fast start for custom games (skip long ban/strategy wait)
    GameRules:SetCustomGameSetupAutoLaunchDelay(0)
    GameRules:SetCustomGameSetupRemainingTime(0)
    GameRules:SetHeroSelectionTime(15.0)
    GameRules:SetHeroSelectPenaltyTime(0.0)
    GameRules:SetStrategyTime(0.0)
    GameRules:SetShowcaseTime(0.0)
    GameRules:SetPreGameTime(3.0)
    GameRules:SetStartingGold(1000)
    GameRules:SetUseUniversalShopMode(true)

    -- Optional: Force a specific hero to skip selection screen completely
    -- GameMode:SetCustomGameForceHero("npc_dota_hero_juggernaut")

    ListenToGameEvent("npc_spawned", Dynamic_Wrap(CCustomGameMode, "OnNPCSpawned"), self)
    ListenToGameEvent("game_rules_state_change", Dynamic_Wrap(CCustomGameMode, "OnStateChanged"), self)

    GameMode:SetThink("OnThink", self, "GlobalThink", 1.0)
end

function CCustomGameMode:OnStateChanged()
    local state = GameRules:State_Get()
    if state == DOTA_GAMERULES_STATE_GAME_IN_PROGRESS then
        -- Start custom waves / gameplay logic here
    end
end

function CCustomGameMode:OnNPCSpawned(keys)
    local npc = EntIndexToHScript(keys.entindex)
    if npc and npc:IsRealHero() and npc.bFirstSpawned == nil then
        npc.bFirstSpawned = true
        -- Initialize hero perks / starting items here
    end
end

function CCustomGameMode:OnThink()
    if GameRules:IsGamePaused() then
        return 1.0
    end
    return 1.0
end
```

---

## 5. Common `.vmap` Entities Reference (For `add_map_entity`)

| Entity `classname` | Purpose | Required `properties` |
| :--- | :--- | :--- |
| `info_player_start_goodguys` | Radiant team spawn point | `{}` |
| `info_player_start_badguys` | Dire team spawn point | `{}` |
| `info_target` | Named coordinate marker for Lua (`Entities:FindByName(nil, targetname)`) | `{"targetname": "wave_spawn_1"}` |
| `ent_dota_tree` | Cuttable Dota 2 tree on map | `{"model": "models/props_tree/tree_oak_01.vmdl"}` (verify model via `search_dota_assets`) |
| `prop_dynamic` | Decorative 3D model on map | `{"model": "<verified_vmdl_path>", "defaultAnim": "idle", "solid": "6"}` |
| `ent_dota_fountain` | Team fountain heal/auras | `{"teamnumber": "2"}` (`2` = Radiant, `3` = Dire) |
| `ent_dota_shop` | Item shop building/zone | `{"shoptype": "0"}` (`0` = Home, `1` = Side, `2` = Secret) |

---

## 6. Panorama UI Root Manifest (`custom_ui_manifest.xml`)

Path: `content/dota_addons/<addon>/panorama/layout/custom_game/custom_ui_manifest.xml`
(Must be compiled via `compile_addon_resource(addon, "panorama/layout/custom_game/custom_ui_manifest.xml")`)

```xml
<root>
    <Panel>
        <CustomUIElement type="Hud" layoutfile="file://{resources}/layout/custom_game/custom_hud.xml" />
    </Panel>
</root>
```
