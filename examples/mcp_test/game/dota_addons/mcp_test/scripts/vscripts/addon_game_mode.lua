-- MCP Test Game Mode: Ring of Fire verification

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
	print( "[MCP_TEST] Initializing game mode..." )

	GameRules:SetCustomGameSetupAutoLaunchDelay( 0 )
	GameRules:EnableCustomGameSetupAutoLaunch( true )
	GameRules:LockCustomGameSetupTeamAssignment( true )

	local gamemode = GameRules:GetGameModeEntity()
	gamemode:SetCustomGameForceHero( "npc_dota_hero_lina" )

	self.hero_initialized = false
	self.player_hero = nil
	self.respawn_wait_ticks = 0

	ListenToGameEvent( "npc_spawned", Dynamic_Wrap( CAddonTemplateGameMode, "OnNPCSpawned" ), self )

	gamemode:SetContextThink( "MCPGlobalThink", function()
		return self:OnThink()
	end, 1.0 )
end

function CAddonTemplateGameMode:SpawnTargetPack( hero )
	if not hero or not hero:IsAlive() then return end

	local origin = hero:GetAbsOrigin()
	local offsets = {
		Vector( 240, 0, 0 ),
		Vector( -240, 0, 0 ),
		Vector( 0, 240, 0 ),
		Vector( 0, -240, 0 ),
	}

	for _, offset in ipairs( offsets ) do
		local spawn_pos = origin + offset
		local unit = CreateUnitByName(
			"npc_dota_creep_badguys_melee",
			spawn_pos,
			true,
			nil,
			nil,
			DOTA_TEAM_BADGUYS
		)
		if unit then
			unit:SetAttackCapability( DOTA_UNIT_CAP_NO_ATTACK )
			FindClearSpaceForUnit( unit, spawn_pos, true )
		end
	end
	print( "[MCP_TEST] Spawned 4 enemy target creeps around hero." )
end

function CAddonTemplateGameMode:OnNPCSpawned( event )
	local npc = EntIndexToHScript( event.entindex )
	if not npc or not npc:IsRealHero() then
		return
	end

	self.player_hero = npc

	if not self.hero_initialized then
		self.hero_initialized = true

		local first_slot = npc:GetAbilityByIndex( 0 )
		if first_slot and first_slot:GetAbilityName() ~= "mcp_ring_of_fire" then
			npc:RemoveAbility( first_slot:GetAbilityName() )
		end

		local ability = npc:FindAbilityByName( "mcp_ring_of_fire" )
		if not ability then
			ability = npc:AddAbility( "mcp_ring_of_fire" )
		end
		if ability then
			ability:SetLevel( 1 )
			print( "[MCP_TEST] Added and leveled mcp_ring_of_fire in slot Q (0)." )
		end

		self:SpawnTargetPack( npc )
	end
end

function CAddonTemplateGameMode:OnThink()
	local state = GameRules:State_Get()
	if state >= DOTA_GAMERULES_STATE_POST_GAME then
		return nil
	end

	if self.player_hero and self.player_hero:IsAlive() then
		-- Keep hero health and mana topped up for convenient repeated ability testing
		self.player_hero:SetHealth( self.player_hero:GetMaxHealth() )
		self.player_hero:GiveMana( 50 )

		-- Check if any enemy targets are alive within 1200 radius; if all dead, respawn after 3 seconds
		local enemies = FindUnitsInRadius(
			self.player_hero:GetTeamNumber(),
			self.player_hero:GetAbsOrigin(),
			nil,
			1200,
			DOTA_UNIT_TARGET_TEAM_ENEMY,
			DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC,
			DOTA_UNIT_TARGET_FLAG_NONE,
			0,
			false
		)

		if #enemies == 0 then
			self.respawn_wait_ticks = self.respawn_wait_ticks + 1
			if self.respawn_wait_ticks >= 3 then
				self.respawn_wait_ticks = 0
				self:SpawnTargetPack( self.player_hero )
			end
		else
			self.respawn_wait_ticks = 0
		end
	end

	return 1.0
end
