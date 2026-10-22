# `mcp_test` — Example Dota 2 Custom Game Addon (Ring of Fire)

This directory contains the source files of the `mcp_test` sandbox addon built and verified exclusively through the `dota2-workshop-mcp` server.

## What It Demonstrates
- **Custom Lua Ability (`mcp_ring_of_fire`)**: Based on `huskar_inner_fire` and `lina_light_strike_array`.
  - After casting (**Q**), a 1.0-second delay modifier (`modifier_mcp_ring_of_fire_delay`) attaches a ground preparation ring (`lina_spell_light_strike_array_ring_collapse.vpcf`, `PATTACH_ABSORIGIN_FOLLOW`) to the caster.
  - When the delay expires, `huskar_inner_fire.vpcf` erupts around the hero's current position and deals magical damage (`110 / 180 / 250 / 320`) to all enemies within a `500` radius.
- **Game Mode (`addon_game_mode.lua`)**:
  - Auto-launches the game, force-picks `npc_dota_hero_lina`, places `mcp_ring_of_fire` into slot **Q**, and keeps hero HP/mana full.
  - Spawns 4 passive target creeps (`npc_dota_creep_badguys_melee` with `DOTA_UNIT_CAP_NO_ATTACK`) around the hero and automatically respawns a new pack 3 seconds after all targets are killed.
- **Auto-Generated Precache (`auto_precache.lua`) & Localization (`addon_russian.txt`, `addon_english.txt`)**.

## How to Deploy into Dota 2
Ask the agent (or run via MCP tools):
1. Call `create_or_configure_addon(addon_name="mcp_test", maps=["template_map"])`.
2. Call `prepare_map_from_template(addon_name="mcp_test", map_name="template_map")` and `compile_addon_resource(addon_name="mcp_test", resource_rel_path="maps/template_map.vmap")`.
3. Copy the files from `examples/mcp_test/game/dota_addons/mcp_test/` into `<dota_path>/game/dota_addons/mcp_test/`.
4. Launch in Dota 2 via `run_console_command("dota_launch_custom_game mcp_test template_map")`.
