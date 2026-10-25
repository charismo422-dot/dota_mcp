-- Lua modifiers used outside abilities/items. addon_game_mode.lua runs only on the server VM, so links made
-- there are unknown to the client ("Attempted to create unknown modifier type ...": no effects, icons, tooltips).
-- This file is required both by addon_game_mode.lua (server) and by an ability script (loaded on the client too).
LinkLuaModifier( "modifier_mcp_damage_meter", "modifiers/modifier_mcp_damage_meter", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_wave_ai", "modifiers/modifier_mcp_wave_ai", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_rift_blessing", "modifiers/modifier_mcp_rift_blessing", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_hunter_ai", "modifiers/modifier_mcp_hunter_ai", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_hunter_power", "modifiers/modifier_mcp_hunter_power", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_boss_ai", "modifiers/modifier_mcp_boss_ai", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_boss_telegraph", "modifiers/modifier_mcp_boss_ai", LUA_MODIFIER_MOTION_NONE )
