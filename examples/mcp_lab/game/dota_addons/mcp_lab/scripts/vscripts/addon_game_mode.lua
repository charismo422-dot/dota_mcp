-- MCP Lab: staged live test addon (see docs/TEST_PLAN.md in dota_mcp)

if CAddonTemplateGameMode == nil then
	CAddonTemplateGameMode = class({})
end

-- Debug console commands are registered at file load so that script_reload picks up new ones
Convars:RegisterCommand( "mcp_lab_status", function()
	local hero = GameRules.AddonTemplate and GameRules.AddonTemplate.hero
	if not hero then print( "[MCP_LAB] status: no hero" ) return end
	local o = hero:GetAbsOrigin()
	print( string.format( "[MCP_LAB] status: hero at %d %d", o.x, o.y ) )
	local units = FindUnitsInRadius( hero:GetTeamNumber(), o, nil, FIND_UNITS_EVERYWHERE, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_INVULNERABLE + DOTA_UNIT_TARGET_FLAG_FOW_VISIBLE, 0, false )
	print( "[MCP_LAB] status: visible enemies=" .. #units )
	local all = FindUnitsInRadius( hero:GetTeamNumber(), o, nil, FIND_UNITS_EVERYWHERE, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_INVULNERABLE, 0, false )
	for _, u in ipairs( all ) do
		local p = u:GetAbsOrigin()
		print( string.format( "[MCP_LAB] status: %s at %d %d dist=%d", u:GetUnitName(), p.x, p.y, ( p - o ):Length2D() ) )
	end
end, "MCP Lab: print hero and enemy positions", 0 )

function Precache( context )
	xpcall(function() require("auto_precache")(context) end, function(err) print("[MCP Precache Error] " .. tostring(err)) end)
	-- Units spawned from Lua are invisible unless their model is precached
	PrecacheUnitByNameSync( "npc_dota_creep_badguys_melee", context )
end

function Activate()
	GameRules.AddonTemplate = CAddonTemplateGameMode()
	GameRules.AddonTemplate:InitGameMode()
end

function CAddonTemplateGameMode:InitGameMode()
	print( "[MCP_LAB] Initializing game mode..." )

	GameRules:SetCustomGameSetupAutoLaunchDelay( 0 )
	GameRules:EnableCustomGameSetupAutoLaunch( true )
	GameRules:LockCustomGameSetupTeamAssignment( true )
	GameRules:SetPreGameTime( 600 )

	GameRules:GetGameModeEntity():SetCustomGameForceHero( "npc_dota_hero_lina" )

	self.hero_initialized = false
	ListenToGameEvent( "npc_spawned", Dynamic_Wrap( CAddonTemplateGameMode, "OnNPCSpawned" ), self )
end

function CAddonTemplateGameMode:SpawnTargets( center )
	local targets = {}
	for _, offset in ipairs({ Vector( 150, 0, 0 ), Vector( -150, 0, 0 ), Vector( 0, 150, 0 ) }) do
		local unit = CreateUnitByName( "npc_dota_creep_badguys_melee", center + offset, true, nil, nil, DOTA_TEAM_BADGUYS )
		if unit then
			unit:SetAttackCapability( DOTA_UNIT_CAP_NO_ATTACK )
			table.insert( targets, unit )
		end
	end
	return targets
end

function CAddonTemplateGameMode:OnNPCSpawned( event )
	local hero = EntIndexToHScript( event.entindex )
	if not hero or not hero:IsRealHero() or self.hero_initialized then
		return
	end
	self.hero_initialized = true

	local first = hero:GetAbilityByIndex( 0 )
	if first then
		hero:RemoveAbility( first:GetAbilityName() )
	end
	local ability = hero:AddAbility( "mcp_frost_nova" )
	ability:SetLevel( 1 )
	print( "[MCP_LAB] mcp_frost_nova added to slot Q" )

	self.hero = hero
	Convars:RegisterCommand( "mcp_lab_autotest", function()
		GameRules.AddonTemplate:RunAutoTest( GameRules.AddonTemplate.hero )
	end, "Re-run MCP Lab ability autotest", 0 )

	self:RunAutoTest( hero )
end

-- Automated check: spawn targets, cast once, verify damage + slow modifier
function CAddonTemplateGameMode:RunAutoTest( hero )
	local ability = hero:FindAbilityByName( "mcp_frost_nova" )
	ability:EndCooldown()
	local center = hero:GetAbsOrigin() + Vector( 400, 0, 0 )
	local targets = self:SpawnTargets( center )
	hero:SetContextThink( "MCPLabAutoCast", function()
		local hp_before = {}
		for i, t in ipairs( targets ) do hp_before[i] = t:GetHealth() end
		hero:GiveMana( 1000 )
		hero:CastAbilityOnPosition( center, ability, hero:GetPlayerOwnerID() )

		hero:SetContextThink( "MCPLabAutoCheck", function()
			local damaged, slowed = 0, 0
			for i, t in ipairs( targets ) do
				if not t:IsAlive() or t:GetHealth() < hp_before[i] then damaged = damaged + 1 end
				if t:IsAlive() and t:HasModifier( "modifier_mcp_frost_nova_slow" ) then slowed = slowed + 1 end
			end
			local result = ( damaged == #targets and slowed == #targets ) and "PASS" or "FAIL"
			print( string.format( "[MCP_LAB] AUTOTEST stage1 %s: targets=%d damaged=%d slowed=%d", result, #targets, damaged, slowed ) )
			return nil
		end, 1.5 )
		return nil
	end, 2.0 )
end
