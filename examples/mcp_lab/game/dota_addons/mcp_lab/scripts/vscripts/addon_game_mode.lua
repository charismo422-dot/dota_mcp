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
		local mods = {}
		for i = 0, u:GetModifierCount() - 1 do table.insert( mods, u:GetModifierNameByIndex( i ) ) end
		print( string.format( "[MCP_LAB] status: %s at %d %d dist=%d mods=%s", u:GetUnitName(), p.x, p.y, ( p - o ):Length2D(), table.concat( mods, "," ) ) )
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

	GameRules:GetGameModeEntity():SetCustomGameForceHero( "npc_dota_hero_crystal_maiden" )

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

	-- Kit comes from npc_heroes_custom.txt (override_hero); log slots to verify the override and level everything
	local slots = {}
	for i = 0, hero:GetAbilityCount() - 1 do
		local a = hero:GetAbilityByIndex( i )
		if a then
			table.insert( slots, i .. "=" .. a:GetAbilityName() )
			if string.sub( a:GetAbilityName(), 1, 4 ) == "mcp_" then a:SetLevel( 1 ) end
		end
	end
	print( "[MCP_LAB] hero " .. hero:GetUnitName() .. " slots: " .. table.concat( slots, " " ) )

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
			self:RunHeroTest( hero, targets )
			return nil
		end, 1.5 )
		return nil
	end, 2.0 )
end

-- Stage 2: hero override (stats, slots), unit-target projectile + stun, passive aura, ultimate thinker
function CAddonTemplateGameMode:RunHeroTest( hero, targets )
	local target = targets[1]
	local bolt = hero:FindAbilityByName( "mcp_ice_bolt" )
	local blizzard = hero:FindAbilityByName( "mcp_blizzard" )
	local checks = {}
	checks.stats = hero:GetBaseMoveSpeed() == 320
	checks.slots = hero:GetAbilityByIndex( 1 ) == bolt and hero:GetAbilityByIndex( 5 ) == blizzard

	local aura_count = 0
	for _, t in ipairs( targets ) do
		if t:IsAlive() and t:HasModifier( "modifier_mcp_frost_aura_debuff" ) then aura_count = aura_count + 1 end
	end
	checks.aura = aura_count > 0

	hero:GiveMana( 1000 )
	bolt:EndCooldown()
	hero:CastAbilityOnTarget( target, bolt, hero:GetPlayerOwnerID() )
	hero:SetContextThink( "MCPLabBoltCheck", function()
		checks.stun = target:IsAlive() and target:HasModifier( "modifier_mcp_ice_bolt_stun" ) and target:IsStunned()

		local hp_before = 0
		for _, t in ipairs( targets ) do if t:IsAlive() then hp_before = hp_before + t:GetHealth() end end
		hero:GiveMana( 1000 )
		blizzard:EndCooldown()
		hero:CastAbilityNoTarget( blizzard, hero:GetPlayerOwnerID() )
		hero:SetContextThink( "MCPLabBlizzardCheck", function()
			local hp_after = 0
			for _, t in ipairs( targets ) do if t:IsAlive() then hp_after = hp_after + t:GetHealth() end end
			checks.ultimate = hp_after < hp_before

			local all_ok, parts = true, {}
			for _, name in ipairs({ "stats", "slots", "aura", "stun", "ultimate" }) do
				all_ok = all_ok and checks[name]
				table.insert( parts, name .. "=" .. tostring( checks[name] ) )
			end
			print( string.format( "[MCP_LAB] AUTOTEST stage2 %s: %s aura_targets=%d", all_ok and "PASS" or "FAIL", table.concat( parts, " " ), aura_count ) )
			return nil
		end, 3.8 )
		return nil
	end, 1.0 )
end
