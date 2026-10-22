-- MCP Lab: staged live test addon (see docs/TEST_PLAN.md in dota_mcp)

if CAddonTemplateGameMode == nil then
	CAddonTemplateGameMode = class({})
end

function Precache( context )
	xpcall(function() require("auto_precache")(context) end, function(err) print("[MCP Precache Error] " .. tostring(err)) end)
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
