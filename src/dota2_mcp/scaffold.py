"""Module 7: Scaffold an ability / item / modifier from a short spec (KV + Lua + localization + precache) in one call."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import vdf
except ImportError:
    vdf = None

from . import addon_manager
from .config import CONFIG
from .vpk_explorer import asset_exists_in_vpk_or_addon, get_sound_event_index, parse_vsndevts_event_names

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BEHAVIORS = ("no_target", "unit_target", "point_aoe", "passive")
TARGET_EFFECTS = ("damage", "stun", "slow")  # applied to enemies hit by an active
SELF_EFFECTS = ("heal",)  # applied to the caster by an active
STAT_EFFECTS = ("bonus_damage", "bonus_armor", "bonus_movespeed")  # buff modifier on the caster

DEFAULT_VALUES = {
    "damage": "100", "heal": "100", "stun_duration": "1", "slow": "30", "duration": "3", "radius": "300",
    "bonus_damage": "20", "bonus_armor": "5", "bonus_movespeed": "15",
}
# Value names each effect needs in AbilityValues
EFFECT_VALUES = {
    "damage": ["damage"], "heal": ["heal"], "stun": ["stun_duration"], "slow": ["slow", "duration"],
    "bonus_damage": ["bonus_damage"], "bonus_armor": ["bonus_armor"], "bonus_movespeed": ["bonus_movespeed"],
}
# Modifier property, Lua getter, sign (slow is a negative movespeed bonus); names verified via script_help2
STAT_PROPERTIES = {
    "bonus_damage": ("MODIFIER_PROPERTY_PREATTACK_BONUS_DAMAGE", "GetModifierPreAttack_BonusDamage", 1),
    "bonus_armor": ("MODIFIER_PROPERTY_PHYSICAL_ARMOR_BONUS", "GetModifierPhysicalArmorBonus", 1),
    "bonus_movespeed": ("MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE", "GetModifierMoveSpeedBonus_Percentage", 1),
    "slow": ("MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE", "GetModifierMoveSpeedBonus_Percentage", -1),
}
# Tooltip labels for AbilityValues ("%" prefix = shown as percent, as in stock abilities_*.txt)
VALUE_LABELS = {
    "russian": {
        "damage": "Урон:", "heal": "Лечение:", "stun_duration": "Оглушение:", "slow": "%Замедление:",
        "duration": "Длительность:", "radius": "Радиус:", "bonus_damage": "Бонус к урону:",
        "bonus_armor": "Бонус к броне:", "bonus_movespeed": "%Бонус к скорости:",
    },
    "english": {
        "damage": "Damage:", "heal": "Heal:", "stun_duration": "Stun Duration:", "slow": "%Slow:",
        "duration": "Duration:", "radius": "Radius:", "bonus_damage": "Bonus Damage:",
        "bonus_armor": "Bonus Armor:", "bonus_movespeed": "%Bonus Move Speed:",
    },
}
BEHAVIOR_KV = {
    "no_target": "DOTA_ABILITY_BEHAVIOR_NO_TARGET",
    "unit_target": "DOTA_ABILITY_BEHAVIOR_UNIT_TARGET",
    "point_aoe": "DOTA_ABILITY_BEHAVIOR_POINT | DOTA_ABILITY_BEHAVIOR_AOE",
    "passive": "DOTA_ABILITY_BEHAVIOR_PASSIVE",
}
LINKS_MODULE = "mcp_scaffold_links"


def _sound_known(name: str, content_addon: Path) -> bool:
    low = name.lower()
    sev_dir = content_addon / "soundevents"
    if sev_dir.exists():
        for f in sev_dir.rglob("*.vsndevts"):
            if low in (n.lower() for n in parse_vsndevts_event_names(f.read_text(encoding="utf-8", errors="replace"))):
                return True
    return low in get_sound_event_index()["events"]


def _find_kv_block(text: str, key: str) -> tuple[int, int] | None:
    """Span of a top-level block `"key" { ... }` inside the root block, or None."""
    m = re.search(rf'^[ \t]*"{re.escape(key)}"\s*\{{', text, re.MULTILINE)
    if not m:
        return None
    depth, i = 0, m.end() - 1
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = text.find("\n", i)
                return m.start(), (len(text) if end == -1 else end + 1)
        i += 1
    return None


def _modifier_lua(mod_name: str, stats: list[str], debuff: bool, purgable: bool, hidden: bool, values: dict[str, str]) -> str:
    lines = [
        f"{mod_name} = class({{}})",
        "",
        f"function {mod_name}:IsHidden() return {str(hidden).lower()} end",
        f"function {mod_name}:IsDebuff() return {str(debuff).lower()} end",
        f"function {mod_name}:IsPurgable() return {str(purgable).lower()} end",
        "",
        f"function {mod_name}:OnCreated( kv )",
        "\tlocal ability = self:GetAbility()",
        "\t-- values come from the ability (AbilityValues) when there is one, else from AddNewModifier params, else defaults",
    ]
    for s in stats:
        default = values.get(s, DEFAULT_VALUES[s]).split()[0]
        lines.append(
            f'\tself.{s} = ( ability and ability:GetSpecialValueFor( "{s}" ) ) or ( kv and tonumber( kv.{s} ) ) or {default}'
        )
    lines += ["end", "", f"function {mod_name}:OnRefresh( kv )", "\tself:OnCreated( kv )", "end", ""]
    if stats:
        props = ", ".join(sorted({STAT_PROPERTIES[s][0] for s in stats}))
        lines += [f"function {mod_name}:DeclareFunctions()", f"\treturn {{ {props} }}", "end", ""]
        for s in stats:
            _, getter, sign = STAT_PROPERTIES[s]
            lines += [f"function {mod_name}:{getter}()", f"\treturn {'-' if sign < 0 else ''}self.{s}", "end", ""]
    return "\n".join(lines)


def _ability_lua(name: str, behavior: str, effects: list[str], buff_mod: str, debuff_mod: str,
                 particle: str, sound: str, values: dict[str, str]) -> str:
    folder = "items" if name.startswith("item_") else "abilities"
    stats = [e for e in effects if e in STAT_EFFECTS]
    out = [
        "-- Scaffolded by dota2-workshop-mcp (scaffold_game_element); edit freely",
        f'require( "{LINKS_MODULE}" )  -- ability scripts also load on the client VM, which needs the links',
    ]
    if stats:
        out.append(f'LinkLuaModifier( "{buff_mod}", "{folder}/{name}", LUA_MODIFIER_MOTION_NONE )')
    if "slow" in effects:
        out.append(f'LinkLuaModifier( "{debuff_mod}", "{folder}/{name}", LUA_MODIFIER_MOTION_NONE )')
    out += ["", f"{name} = class({{}})", ""]

    if behavior == "passive":
        if stats:
            out += [f"function {name}:GetIntrinsicModifierName()", f'\treturn "{buff_mod}"', "end", ""]
    else:
        if behavior in ("point_aoe", "no_target") and "radius" in values:
            out += [f"function {name}:GetAOERadius()", '\treturn self:GetSpecialValueFor( "radius" )', "end", ""]
        out += [f"function {name}:OnSpellStart()", "\tif not IsServer() then return end", "",
                "\tlocal caster = self:GetCaster()"]
        hits = any(e in TARGET_EFFECTS for e in effects)
        if behavior == "unit_target":
            out += ["\tlocal target = self:GetCursorTarget()",
                    "\tif target:TriggerSpellAbsorb( self ) then return end",
                    "\tlocal center = target:GetAbsOrigin()"]
            if hits:
                out.append("\tlocal targets = { target }")
        else:
            out.append("\tlocal center = " + ("self:GetCursorPosition()" if behavior == "point_aoe" else "caster:GetAbsOrigin()"))
            if hits:
                out += ["\tlocal targets = FindUnitsInRadius( caster:GetTeamNumber(), center, nil,",
                        '\t\tself:GetSpecialValueFor( "radius" ), DOTA_UNIT_TARGET_TEAM_ENEMY,',
                        "\t\tDOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_NONE, 0, false )"]
        if particle:
            out += ["", "\t-- CP0 only; check other control points with inspect_particle",
                    f'\tlocal pfx = ParticleManager:CreateParticle( "{particle}", PATTACH_WORLDORIGIN, nil )',
                    "\tParticleManager:SetParticleControl( pfx, 0, center )",
                    "\tParticleManager:ReleaseParticleIndex( pfx )"]
        if sound:
            out.append(f'\tEmitSoundOnLocationWithCaster( center, "{sound}", caster )')
        if hits:
            out += ["", "\tfor _, unit in pairs( targets ) do"]
            if "damage" in effects:
                out += ["\t\tApplyDamage({ victim = unit, attacker = caster, ability = self,",
                        '\t\t\tdamage = self:GetSpecialValueFor( "damage" ), damage_type = self:GetAbilityDamageType() })']
            if "stun" in effects:
                out.append('\t\tunit:AddNewModifier( caster, self, "modifier_stunned", { duration = self:GetSpecialValueFor( "stun_duration" ) } )')
            if "slow" in effects:
                out.append(f'\t\tunit:AddNewModifier( caster, self, "{debuff_mod}", {{ duration = self:GetSpecialValueFor( "duration" ) }} )')
            out.append("\tend")
        if "heal" in effects:
            out += ["", '\tcaster:Heal( self:GetSpecialValueFor( "heal" ), self )',
                    '\tSendOverheadEventMessage( nil, OVERHEAD_ALERT_HEAL, caster, self:GetSpecialValueFor( "heal" ), nil )']
        if stats:
            out += ["", f'\tcaster:AddNewModifier( caster, self, "{buff_mod}", {{ duration = self:GetSpecialValueFor( "duration" ) }} )']
        out += ["end", ""]

    out.append("-" * 80)
    out.append("")
    if stats:
        out.append(_modifier_lua(buff_mod, stats, False, behavior != "passive", behavior == "passive", values))
    if "slow" in effects:
        out.append(_modifier_lua(debuff_mod, ["slow"], True, True, False, values))
    return "\n".join(out)


def _kv_block(name: str, behavior: str, effects: list[str], values: dict[str, str], texture: str,
              cooldown: str, mana_cost: str, cast_range: str, item_cost: int, cast_animation: str, sound: str) -> str:
    is_item = name.startswith("item_")
    folder = "items" if is_item else "abilities"
    kv = [
        f'\t"{name}"', "\t{",
        f'\t\t"BaseClass"\t\t\t\t\t"{"item_lua" if is_item else "ability_lua"}"',
        f'\t\t"ScriptFile"\t\t\t\t\t"{folder}/{name}"',
        f'\t\t"AbilityBehavior"\t\t\t"{BEHAVIOR_KV[behavior]}"',
    ]
    if texture:
        kv.append(f'\t\t"AbilityTextureName"\t\t\t"{texture}"')
    if "damage" in effects:
        kv.append('\t\t"AbilityUnitDamageType"\t\t"DAMAGE_TYPE_MAGICAL"')
    if behavior == "unit_target":
        kv += ['\t\t"AbilityUnitTargetTeam"\t\t"DOTA_UNIT_TARGET_TEAM_ENEMY"',
               '\t\t"AbilityUnitTargetType"\t\t"DOTA_UNIT_TARGET_HERO | DOTA_UNIT_TARGET_BASIC"']
    if any(e in TARGET_EFFECTS for e in effects):
        kv.append('\t\t"SpellImmunityType"\t\t\t"SPELL_IMMUNITY_ENEMIES_NO"')
    if cast_animation and not is_item and behavior != "passive":
        kv.append(f'\t\t"AbilityCastAnimation"\t\t"{cast_animation}"')
    if sound:
        kv.append(f'\t\t"AbilitySound"\t\t\t\t"{sound}"')
    if is_item:
        kv += [f'\t\t"ItemCost"\t\t\t\t\t"{item_cost}"', '\t\t"ItemPurchasable"\t\t\t"1"']
    kv += ["", '\t\t"AbilityValues"', "\t\t{"]
    if behavior != "passive":
        kv += [f'\t\t\t"AbilityCooldown"\t\t"{cooldown}"', f'\t\t\t"AbilityManaCost"\t\t"{mana_cost}"']
        if behavior != "no_target":
            kv.append(f'\t\t\t"AbilityCastRange"\t\t"{cast_range}"')
    for k, v in values.items():
        kv.append(f'\t\t\t"{k}"\t\t\t\t"{v}"')
    kv += ["\t\t}", "\t}", ""]
    return "\n".join(kv)


def _ensure_links_module(vscripts: Path) -> Path:
    links = vscripts / f"{LINKS_MODULE}.lua"
    if not links.exists():
        links.write_text(
            "-- Lua modifier links for scaffolded standalone modifiers (scaffold_game_element).\n"
            "-- Required by addon_game_mode.lua (server) and by every scaffolded ability/item (client VM too).\n",
            encoding="utf-8",
        )
    gm = vscripts / "addon_game_mode.lua"
    if gm.exists():
        text = gm.read_text(encoding="utf-8", errors="replace")
        if LINKS_MODULE not in text:
            gm.write_text(f'require( "{LINKS_MODULE}" )  -- scaffold_game_element: modifier links\n' + text, encoding="utf-8")
    return links


def scaffold_game_element(
    addon_name: str,
    kind: str,
    name: str,
    title: str,
    description: str,
    behavior: str = "no_target",
    effects: list[str] | None = None,
    values: dict[str, str] | None = None,
    texture: str = "",
    particle: str = "",
    sound: str = "",
    cooldown: str = "10",
    mana_cost: str = "50",
    cast_range: str = "600",
    item_cost: int = 500,
    cast_animation: str = "ACT_DOTA_CAST_ABILITY_1",
    language: str = "russian",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create an ability, item or standalone modifier in the addon: KV block, Lua, localization, precache."""
    if not CONFIG.is_valid or not CONFIG.game_addons_dir or not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 root directory not found."}
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}
    game_addon = CONFIG.game_addons_dir / addon_name
    content_addon = CONFIG.content_addons_dir / addon_name
    if not game_addon.exists():
        return {"ok": False, "error": f"Addon '{addon_name}' does not exist."}

    kind = kind.lower().strip()
    effects = [e.lower().strip() for e in (effects or [])]
    errors: list[str] = []
    if kind not in ("ability", "item", "modifier"):
        errors.append("kind must be 'ability', 'item' or 'modifier'")
    if not NAME_RE.match(name):
        errors.append("name must be lowercase snake_case (a-z, 0-9, _)")
    if kind == "item" and not name.startswith("item_"):
        errors.append("item names must start with 'item_'")
    if kind == "modifier" and not name.startswith("modifier_"):
        errors.append("modifier names must start with 'modifier_'")
    if behavior not in BEHAVIORS:
        errors.append(f"behavior must be one of {list(BEHAVIORS)}")
    known = TARGET_EFFECTS + SELF_EFFECTS + STAT_EFFECTS
    bad = [e for e in effects if e not in known]
    if bad:
        errors.append(f"unknown effects {bad}; supported: {list(known)}")
    if not effects:
        errors.append("at least one effect is required")
    if kind == "modifier" and any(e not in STAT_EFFECTS + ("slow",) for e in effects):
        errors.append(f"a standalone modifier supports only {list(STAT_EFFECTS) + ['slow']}")
    if behavior == "passive" and any(e not in STAT_EFFECTS for e in effects):
        errors.append(f"a passive supports only {list(STAT_EFFECTS)}")
    if particle and not asset_exists_in_vpk_or_addon(particle, addon_name):
        errors.append(f"particle not found in VPK/addon: {particle} (use search_dota_assets)")
    if sound:
        try:
            if not _sound_known(sound, content_addon):
                errors.append(f"unknown sound event: {sound} (use search_sound_events)")
        except Exception as exc:
            errors.append(f"sound index unavailable: {exc}")
    if errors:
        return {"ok": False, "errors": errors}

    # AbilityValues: what the effects need, plus radius for area actives, plus duration for timed buffs
    needed: list[str] = []
    for e in effects:
        needed += EFFECT_VALUES[e]
    if kind != "modifier":
        if behavior in ("no_target", "point_aoe") and any(e in TARGET_EFFECTS for e in effects):
            needed.append("radius")
        if behavior != "passive" and any(e in STAT_EFFECTS for e in effects):
            needed.append("duration")
    merged = {k: str((values or {}).get(k, DEFAULT_VALUES[k])) for k in dict.fromkeys(needed)}
    merged.update({k: str(v) for k, v in (values or {}).items() if k not in merged})

    vscripts = game_addon / "scripts" / "vscripts"
    links = _ensure_links_module(vscripts)
    written: list[str] = []
    loc: dict[str, str] = {}

    if kind == "modifier":
        lua_file = vscripts / "modifiers" / f"{name}.lua"
        if lua_file.exists() and not overwrite:
            return {"ok": False, "errors": [f"{lua_file.name} already exists (pass overwrite=True)"]}
        lua_file.parent.mkdir(parents=True, exist_ok=True)
        stats = [e for e in effects if e in STAT_EFFECTS or e == "slow"]
        lua_file.write_text(
            "-- Scaffolded by dota2-workshop-mcp (scaffold_game_element); edit freely\n"
            "-- Apply from Lua: unit:AddNewModifier( caster, nil, \"" + name + "\", { duration = 5 } )\n\n"
            + _modifier_lua(name, stats, effects == ["slow"], True, False, merged),
            encoding="utf-8",
        )
        written.append(str(lua_file))
        link_line = f'LinkLuaModifier( "{name}", "modifiers/{name}", LUA_MODIFIER_MOTION_NONE )'
        lt = links.read_text(encoding="utf-8")
        if link_line not in lt:
            links.write_text(lt + link_line + "\n", encoding="utf-8")
        loc[f"DOTA_Tooltip_{name}"] = title
        loc[f"DOTA_Tooltip_{name}_Description"] = description
    else:
        kv_file = game_addon / "scripts" / "npc" / ("npc_items_custom.txt" if kind == "item" else "npc_abilities_custom.txt")
        kv_file.parent.mkdir(parents=True, exist_ok=True)
        text = kv_file.read_text(encoding="utf-8") if kv_file.exists() else '"DOTAAbilities"\n{\n\t"Version"\t\t"1"\n}\n'
        span = _find_kv_block(text, name)
        if span and not overwrite:
            return {"ok": False, "errors": [f"'{name}' already exists in {kv_file.name} (pass overwrite=True)"]}
        if span:
            text = text[: span[0]] + text[span[1]:]
        block = _kv_block(name, behavior, effects, merged, texture, cooldown, mana_cost, cast_range,
                          item_cost, cast_animation, sound)
        close = text.rstrip().rfind("}")
        new_text = text[:close].rstrip("\n") + "\n\n\t// Scaffolded by scaffold_game_element\n" + block + "}\n"
        try:
            vdf.loads(new_text)
        except Exception as exc:
            return {"ok": False, "errors": [f"generated KV does not parse, nothing written: {exc}"]}
        kv_file.write_text(new_text, encoding="utf-8")
        written.append(str(kv_file))

        folder = "items" if kind == "item" else "abilities"
        lua_file = vscripts / folder / f"{name}.lua"
        lua_file.parent.mkdir(parents=True, exist_ok=True)
        buff_mod, debuff_mod = f"modifier_{name}_buff", f"modifier_{name}_debuff"
        lua_file.write_text(_ability_lua(name, behavior, effects, buff_mod, debuff_mod, particle, sound, merged), encoding="utf-8")
        written.append(str(lua_file))

        prefix = f"DOTA_Tooltip_ability_{name}"
        loc[prefix] = title
        loc[f"{prefix}_Description"] = description
        labels = VALUE_LABELS.get(language.lower(), VALUE_LABELS["english"])
        for k in merged:
            if k in labels:
                loc[f"{prefix}_{k}"] = labels[k]
        if any(e in STAT_EFFECTS for e in effects):
            loc[f"DOTA_Tooltip_{buff_mod}"] = title
            loc[f"DOTA_Tooltip_{buff_mod}_Description"] = description
        if "slow" in effects:
            loc[f"DOTA_Tooltip_{debuff_mod}"] = title
            loc[f"DOTA_Tooltip_{debuff_mod}_Description"] = labels["slow"].lstrip("%").rstrip(":")

    loc_res = addon_manager.upsert_localization(addon_name, language, loc)
    check = addon_manager.validate_and_sync_precache(addon_name)
    return {
        "ok": bool(loc_res.get("ok")) and bool(check.get("ok")),
        "kind": kind,
        "name": name,
        "files_written": written,
        "ability_values": merged,
        "localization_keys": sorted(loc),
        "precache": {
            "ok": check.get("ok"),
            "kv_syntax_errors": check.get("kv_syntax_errors"),
            "missing_or_hallucinated_assets": check.get("missing_or_hallucinated_assets"),
            "unknown_sound_events": check.get("unknown_sound_events"),
        },
        "next": "script_reload (or relaunch), then test the element in game",
    }
