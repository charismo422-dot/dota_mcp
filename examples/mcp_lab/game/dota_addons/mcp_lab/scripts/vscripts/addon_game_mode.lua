-- MCP Lab: staged live test addon (see docs/TEST_PLAN.md in dota_mcp)

if CAddonTemplateGameMode == nil then
	CAddonTemplateGameMode = class({})
end

require( "mcp_lab_links" )

local WAVE_SPAWNERS = { "lab_spawn_west", "lab_spawn_east" }  -- info_target entities placed with add_map_entity

local function DamageTaken( unit )
	local meter = unit:FindModifierByName( "modifier_mcp_damage_meter" )
	return meter and meter.total or 0
end

-- ListenToGameEvent registrations SURVIVE script_reload and stack up (one extra call per reload),
-- so the previous listener id is kept on GameRules (engine object, persists) and removed before re-registering
if GameRules.mcp_lab_kill_listener then
	StopListeningToGameEvent( GameRules.mcp_lab_kill_listener )
end
GameRules.mcp_lab_kill_listener = ListenToGameEvent( "entity_killed", function( event )
	if GameRules.AddonTemplate then GameRules.AddonTemplate:OnEntityKilled( event ) end
end, nil )

-- Debug console commands are registered at file load so that script_reload picks up new ones
Convars:RegisterCommand( "mcp_lab_status", function()
	local hero = GameRules.AddonTemplate and GameRules.AddonTemplate.hero
	if not hero then print( "[MCP_LAB] status: no hero" ) return end
	local o = hero:GetAbsOrigin()
	print( string.format( "[MCP_LAB] status: hero at %d %d; world X %d..%d Y %d..%d", o.x, o.y, GetWorldMinX(), GetWorldMaxX(), GetWorldMinY(), GetWorldMaxY() ) )
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

-- Minimap capture helper: dota_minimap_create bakes visible units into the image,
-- so remove spawned test units and park the hero outside the minimap bounds first ("mcp_lab_minimap_prep 0" to return).
Convars:RegisterCommand( "mcp_lab_minimap_prep", function( _, restore )
	local hero = GameRules.AddonTemplate and GameRules.AddonTemplate.hero
	if not hero then return end
	if restore == "0" then
		FindClearSpaceForUnit( hero, Vector( 0, 0, 0 ), true )
		print( "[MCP_LAB] minimap prep: hero restored" )
		return
	end
	for _, u in ipairs( FindUnitsInRadius( hero:GetTeamNumber(), Vector( 0, 0, 0 ), nil, FIND_UNITS_EVERYWHERE, DOTA_UNIT_TARGET_TEAM_BOTH,
		DOTA_UNIT_TARGET_ALL, DOTA_UNIT_TARGET_FLAG_INVULNERABLE, 0, false ) ) do
		if u ~= hero then UTIL_Remove( u ) end
	end
	hero:SetAbsOrigin( Vector( 6000, 6000, 0 ) )
	print( "[MCP_LAB] minimap prep: units removed, hero parked outside bounds" )
end, "MCP Lab: clear units before dota_minimap_create", 0 )

-- "mcp_lab_waves <seconds>" starts timed waves, "mcp_lab_waves 0" stops them
Convars:RegisterCommand( "mcp_lab_waves", function( _, interval )
	GameRules.AddonTemplate:SetWaveInterval( tonumber( interval ) or 30 )
end, "MCP Lab: start/stop timed waves", 0 )

Convars:RegisterCommand( "mcp_lab_autotest", function()
	GameRules.AddonTemplate:RunAutoTest( GameRules.AddonTemplate.hero )
end, "MCP Lab: run all autotests (stage 1 -> 2 -> 3 -> 4)", 0 )

-- Visual demo for the player: an enemy Enigma appears and uses Void Shard on the player's hero,
-- so the silence is visible on the player's own ability bar
Convars:RegisterCommand( "mcp_lab_demo_silence", function()
	local hero = GameRules.AddonTemplate.hero
	local pos = hero:GetAbsOrigin() + Vector( 600, 0, 0 )
	local enemy = CreateUnitByName( "npc_dota_hero_enigma", pos, true, nil, nil, DOTA_TEAM_BADGUYS )
	enemy:SetIdleAcquire( false )
	local item = enemy:AddItemByName( "item_mcp_void_shard" )
	enemy:SetContextThink( "MCPLabDemoCast", function()
		enemy:GiveMana( 1000 )
		enemy:CastAbilityOnPosition( hero:GetAbsOrigin(), item, -1 )
		enemy:SetContextThink( "MCPLabDemoCheck", function()
			print( "[MCP_LAB] demo silence: player hero silenced=" .. tostring( hero:IsSilenced() ) )
			return nil
		end, 1.3 )
		enemy:SetContextThink( "MCPLabDemoCleanup", function()
			UTIL_Remove( enemy )
			return nil
		end, 6.0 )
		return nil
	end, 1.5 )
	print( "[MCP_LAB] demo silence: enemy Enigma spawned" )
end, "MCP Lab: enemy uses Void Shard on the player's hero", 0 )

-- Stage 5: Lua -> JS -> Lua round trip (JS acks every ping) and kill counter / energy feeding the HUD
Convars:RegisterCommand( "mcp_lab_autotest5", function()
	local gm = GameRules.AddonTemplate
	local checks = {}
	local kills_before, energy_before = gm.hud_kills, gm.hud_energy
	local ping = RandomInt( 1000, 999999 )
	gm:SendHudUpdate( ping )

	local units = gm:SpawnWave( 1, false )
	-- Kill with damage: ForceKill() did not raise entity_killed for these creatures
	gm.hero:SetContextThink( "MCPLabHudKill", function()
		ApplyDamage({ victim = units[1], attacker = gm.hero, damage = 99999, damage_type = DAMAGE_TYPE_PURE })
		return nil
	end, 0.5 )

	gm.hero:SetContextThink( "MCPLabHudCheck", function()
		-- Exactly +1: catches stacked listeners after script_reload
		checks.kill_counted = gm.hud_kills == kills_before + 1 and ( gm.hud_energy > energy_before or gm.hud_energy == 100 )
		print( string.format( "[MCP_LAB] stage5 kills %d -> %d", kills_before, gm.hud_kills ) )
		checks.js_roundtrip = gm.hud_acks[ tostring( ping ) ] == true
		gm:ClearWaveUnits()
		local all_ok, parts = true, {}
		for _, name in ipairs({ "kill_counted", "js_roundtrip" }) do
			all_ok = all_ok and checks[name]
			table.insert( parts, name .. "=" .. tostring( checks[name] ) )
		end
		print( string.format( "[MCP_LAB] AUTOTEST stage5 %s: %s kills=%d energy=%d", all_ok and "PASS" or "FAIL", table.concat( parts, " " ), gm.hud_kills, gm.hud_energy ) )
		return nil
	end, 1.5 )
end, "MCP Lab: stage 5 autotest (Panorama HUD events)", 0 )

-- Stage 5b: world-space Panorama — floating damage numbers, overhead charges, NPC dialog with a choice
Convars:RegisterCommand( "mcp_lab_autotest5b", function()
	local gm = GameRules.AddonTemplate
	local hero = gm.hero
	local checks = {}
	local home = hero:GetAbsOrigin()
	local function probe( tag )
		local ping = RandomInt( 1000, 999999 )
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_world_probe", { ping = ping } )
		return tostring( ping )
	end

	-- 1) hit a dummy -> floating numbers must appear; overhead charges must track the hero
	local dummy = CreateUnitByName( "npc_dota_hero_target_dummy", home + Vector( 250, 0, 0 ), true, nil, nil, DOTA_TEAM_NEUTRALS )
	dummy:SetIdleAcquire( false )
	dummy:AddNewModifier( dummy, nil, "modifier_mcp_damage_meter", {} )
	hero:SetContextThink( "MCPLab5bHit", function()
		ApplyDamage({ victim = dummy, attacker = hero, damage = 123, damage_type = DAMAGE_TYPE_MAGICAL })
		local p1 = probe()
		hero:SetContextThink( "MCPLab5bProbe1", function()
			local a = ( gm.world_acks or {} )[ p1 ]
			checks.floating_numbers = a ~= nil and a.floats > 0
			checks.overhead = a ~= nil and a.overhead == 1

			-- 2) walk up to the keeper -> dialog opens; JS simulates pressing option 1
			FindClearSpaceForUnit( hero, gm.keeper:GetAbsOrigin() + Vector( 150, -100, 0 ), true )
			hero:SetContextThink( "MCPLab5bDialog", function()
				local p2 = probe()
				hero:SetContextThink( "MCPLab5bProbe2", function()
					local b = ( gm.world_acks or {} )[ p2 ]
					checks.dialog_open = b ~= nil and b.dialog == 1
					CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dialog_autochoose", { option = 1 } )
					hero:SetContextThink( "MCPLab5bChoice", function()
						checks.choice_applied = hero:HasModifier( "modifier_mcp_rift_blessing" )
						FindClearSpaceForUnit( hero, home, true )
						UTIL_Remove( dummy )
						local all_ok, parts = true, {}
						for _, name in ipairs({ "floating_numbers", "overhead", "dialog_open", "choice_applied" }) do
							all_ok = all_ok and checks[name]
							table.insert( parts, name .. "=" .. tostring( checks[name] ) )
						end
						print( "[MCP_LAB] AUTOTEST stage5b " .. ( all_ok and "PASS" or "FAIL" ) .. ": " .. table.concat( parts, " " ) )
						return nil
					end, 1.0 )
					return nil
				end, 0.4 )
				return nil
			end, 0.8 )
			return nil
		end, 0.4 )
		return nil
	end, 0.3 )
end, "MCP Lab: stage 5b autotest (world-space Panorama)", 0 )

Convars:RegisterCommand( "mcp_lab_autotest4", function()
	GameRules.AddonTemplate:RunItemTest( GameRules.AddonTemplate.hero )
end, "MCP Lab: stage 4 autotest (custom item: stats, rift pull, silence)", 0 )

Convars:RegisterCommand( "mcp_lab_autotest3", function()
	GameRules.AddonTemplate:RunWaveTest( GameRules.AddonTemplate.hero )
end, "MCP Lab: stage 3 autotest (waves, spawners, AI, elite slam)", 0 )

function Precache( context )
	xpcall(function() require("auto_precache")(context) end, function(err) print("[MCP Precache Error] " .. tostring(err)) end)
	-- Units spawned from Lua are invisible unless their model is precached
	PrecacheUnitByNameSync( "npc_dota_hero_target_dummy", context )
	PrecacheUnitByNameSync( "npc_mcp_void_imp", context )
	PrecacheUnitByNameSync( "npc_mcp_rift_giant", context )
	PrecacheUnitByNameSync( "npc_dota_hero_enigma", context )
	PrecacheUnitByNameSync( "npc_mcp_rift_keeper", context )
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
	GameRules:SetStartingGold( 99999 )  -- playtest: every custom item must be buyable right away

	GameRules:GetGameModeEntity():SetCustomGameForceHero( "npc_dota_hero_crystal_maiden" )

	self.hero_initialized = false
	ListenToGameEvent( "npc_spawned", Dynamic_Wrap( CAddonTemplateGameMode, "OnNPCSpawned" ), self )

	-- Stage 5: Panorama HUD (content/panorama/.../mcp_lab_hud.*), events in both directions
	self.hud_kills, self.hud_energy, self.hud_acks = 0, 0, {}
	CustomGameEventManager:RegisterListener( "mcp_lab_summon_wave", function(...) return self:OnHudSummonWave( ... ) end )
	CustomGameEventManager:RegisterListener( "mcp_lab_hud_ack", function(...) return self:OnHudAck( ... ) end )
	CustomGameEventManager:RegisterListener( "mcp_lab_dialog_choice", function(...) return self:OnDialogChoice( ... ) end )
	CustomGameEventManager:RegisterListener( "mcp_lab_world_ack", function(...) return self:OnWorldAck( ... ) end )
	GameRules:GetGameModeEntity():SetContextThink( "MCPLabHud", function()
		self:SendHudUpdate()
		return 0.5
	end, 1 )
end

function CAddonTemplateGameMode:SendHudUpdate( ping )
	local next_wave = -1
	if self.next_wave_time then
		next_wave = math.max( 0, math.ceil( self.next_wave_time - GameRules:GetGameTime() ) )
	end
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_hud", { energy = self.hud_energy, kills = self.hud_kills, next_wave = next_wave, ping = ping } )
end

function CAddonTemplateGameMode:OnEntityKilled( event )
	local unit = EntIndexToHScript( event.entindex_killed )
	if unit and ( unit:GetUnitName() == "npc_mcp_void_imp" or unit:GetUnitName() == "npc_mcp_rift_giant" ) then
		self:OnWaveUnitKilled( unit )
	end
end

function CAddonTemplateGameMode:OnWaveUnitKilled( unit )
	self.hud_kills = self.hud_kills + 1
	self.hud_energy = math.min( 100, self.hud_energy + ( unit:GetUnitName() == "npc_mcp_rift_giant" and 40 or 10 ) )
	self:SendHudUpdate()
end

-- Button in the HUD: summon a wave right now (spends the energy if it is full)
function CAddonTemplateGameMode:OnHudSummonWave( event_source_index, data )
	self.wave_number = ( self.wave_number or 0 ) + 1
	self:SpawnWave( self.wave_number, self.hud_energy >= 100 )
	if self.hud_energy >= 100 then self.hud_energy = 0 end
	self.hud_summons = ( self.hud_summons or 0 ) + 1
	print( "[MCP_LAB] HUD button: wave summoned" )
	self:SendHudUpdate()
end

function CAddonTemplateGameMode:OnHudAck( event_source_index, data )
	self.hud_acks[ tostring( data.ping ) ] = true
end

-- World-space UI script reports what it currently shows (used by the stage 5b autotest)
function CAddonTemplateGameMode:OnWorldAck( event_source_index, data )
	self.world_acks = self.world_acks or {}
	self.world_acks[ tostring( data.ping ) ] = data
end

function CAddonTemplateGameMode:SpawnTargets( center )
	local targets = {}
	for _, offset in ipairs({ Vector( 150, 0, 0 ), Vector( -150, 0, 0 ), Vector( 0, 150, 0 ) }) do
		-- Training dummy hero, set up exactly like Valve's hero_demo (5000 HP, no damage, never acquires targets).
		-- npc_dota_target_dummy from npc_units.txt cannot be created in custom games ("entity class is NULL").
		local unit = CreateUnitByName( "npc_dota_hero_target_dummy", center + offset, true, nil, nil, DOTA_TEAM_NEUTRALS )
		if unit then
			unit:SetAbilityPoints( 0 )
			unit:Hold()
			unit:SetIdleAcquire( false )
			unit:SetAcquisitionRange( 0 )
			unit:AddNewModifier( unit, nil, "modifier_mcp_damage_meter", {} )
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

	-- Autotests are NOT started here: a manual playtest must begin with a clean arena.
	-- The agent runs them on demand ("mcp_lab_autotest" = all stages, "mcp_lab_autotest3/4" = single stage).
	self.hero = hero
	self:SpawnRiftKeeper( hero:GetAbsOrigin() + Vector( -500, 350, 0 ) )
end

--------------------------------------------------------------------------------
-- Stage 5b: Rift Keeper NPC with a Panorama dialog (opens when the hero walks up to it)
--------------------------------------------------------------------------------

function CAddonTemplateGameMode:SpawnRiftKeeper( pos )
	local keeper = CreateUnitByName( "npc_mcp_rift_keeper", pos, true, nil, nil, DOTA_TEAM_GOODGUYS )
	keeper:AddNewModifier( keeper, nil, "modifier_invulnerable", {} )
	keeper:SetForwardVector( Vector( 1, -1, 0 ):Normalized() )
	self.keeper = keeper
	self.dialog_open = false
	GameRules:GetGameModeEntity():SetContextThink( "MCPLabKeeperDialog", function()
		return self:UpdateKeeperDialog()
	end, 0.25 )
end

function CAddonTemplateGameMode:UpdateKeeperDialog()
	if not IsValidEntity( self.keeper ) or not IsValidEntity( self.hero ) then return nil end
	local dist = ( self.hero:GetAbsOrigin() - self.keeper:GetAbsOrigin() ):Length2D()
	if not self.dialog_open and dist < 320 then
		self.dialog_open = true
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dialog", {
			action = "open", npc = self.keeper:entindex(),
			speaker = "#mcp_lab_keeper_name", text = "#mcp_lab_keeper_greet",
			opt1 = "#mcp_lab_keeper_opt_gift", opt2 = "#mcp_lab_keeper_opt_leave",
		} )
	elseif self.dialog_open and dist > 520 then
		self.dialog_open = false
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dialog", { action = "close" } )
	end
	return 0.25
end

function CAddonTemplateGameMode:OnDialogChoice( event_source_index, data )
	if tonumber( data.option ) == 1 then
		self.hero:AddNewModifier( self.hero, nil, "modifier_mcp_rift_blessing", { duration = 15 } )
		self.hud_energy = math.min( 100, self.hud_energy + 50 )
		self:SendHudUpdate()
		EmitSoundOn( "Hero_Enigma.Black_Hole.Stop", self.hero )
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dialog", { action = "reply", text = "#mcp_lab_keeper_reply_gift" } )
	else
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dialog", { action = "reply", text = "#mcp_lab_keeper_reply_leave" } )
	end
	print( "[MCP_LAB] dialog choice " .. tostring( data.option ) )
end

-- Automated check: spawn targets, cast once, verify damage + slow modifier
function CAddonTemplateGameMode:RunAutoTest( hero )
	local ability = hero:FindAbilityByName( "mcp_frost_nova" )
	ability:EndCooldown()
	local center = hero:GetAbsOrigin() + Vector( 400, 0, 0 )
	local targets = self:SpawnTargets( center )
	hero:SetContextThink( "MCPLabAutoCast", function()
		local hp_before = {}
		for i, t in ipairs( targets ) do hp_before[i] = DamageTaken( t ) end
		hero:GiveMana( 1000 )
		hero:CastAbilityOnPosition( center, ability, hero:GetPlayerOwnerID() )

		hero:SetContextThink( "MCPLabAutoCheck", function()
			local damaged, slowed = 0, 0
			for i, t in ipairs( targets ) do
				if DamageTaken( t ) > hp_before[i] then damaged = damaged + 1 end
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

		local dmg_before = 0
		for _, t in ipairs( targets ) do dmg_before = dmg_before + DamageTaken( t ) end
		hero:GiveMana( 1000 )
		blizzard:EndCooldown()
		hero:CastAbilityNoTarget( blizzard, hero:GetPlayerOwnerID() )
		hero:SetContextThink( "MCPLabBlizzardCheck", function()
			local dmg_after = 0
			for _, t in ipairs( targets ) do dmg_after = dmg_after + DamageTaken( t ) end
			checks.ultimate = dmg_after > dmg_before

			local all_ok, parts = true, {}
			for _, name in ipairs({ "stats", "slots", "aura", "stun", "ultimate" }) do
				all_ok = all_ok and checks[name]
				table.insert( parts, name .. "=" .. tostring( checks[name] ) )
			end
			print( string.format( "[MCP_LAB] AUTOTEST stage2 %s: %s aura_targets=%d", all_ok and "PASS" or "FAIL", table.concat( parts, " " ), aura_count ) )
			self:RunWaveTest( hero )
			return nil
		end, 3.8 )
		return nil
	end, 1.0 )
end

--------------------------------------------------------------------------------
-- Stage 3: waves from map spawners, custom AI, telegraphed elite attack
--------------------------------------------------------------------------------

function CAddonTemplateGameMode:SpawnWave( wave_number, force_giant )
	self.wave_units = self.wave_units or {}
	self.waves_spawned = ( self.waves_spawned or 0 ) + 1
	local spawned = {}
	for _, name in ipairs( WAVE_SPAWNERS ) do
		local spawner = Entities:FindByName( nil, name )
		if spawner then
			local origin = spawner:GetAbsOrigin()
			for i = 1, 1 + wave_number do
				local imp = CreateUnitByName( "npc_mcp_void_imp", origin + RandomVector( 120 ), true, nil, nil, DOTA_TEAM_BADGUYS )
				imp:SetRenderColor( 170, 60, 255 )  -- void purple, so the reused creep model reads as a new unit
				imp:AddNewModifier( imp, nil, "modifier_mcp_wave_ai", {} )
				imp:AddNewModifier( imp, nil, "modifier_mcp_damage_meter", {} )  -- floating damage numbers
				table.insert( spawned, imp )
			end
			if force_giant or wave_number % 3 == 0 then
				local giant = CreateUnitByName( "npc_mcp_rift_giant", origin, true, nil, nil, DOTA_TEAM_BADGUYS )
				giant:SetRenderColor( 255, 90, 90 )
				giant:FindAbilityByName( "mcp_giant_slam" ):SetLevel( 1 )
				giant:AddNewModifier( giant, nil, "modifier_mcp_wave_ai", {} )
				giant:AddNewModifier( giant, nil, "modifier_mcp_damage_meter", {} )
				table.insert( spawned, giant )
				force_giant = false  -- one giant per wave
			end
		else
			print( "[MCP_LAB] wave: spawner not found: " .. name )
		end
	end
	for _, u in ipairs( spawned ) do table.insert( self.wave_units, u ) end
	print( string.format( "[MCP_LAB] wave %d spawned: %d units", wave_number, #spawned ) )
	return spawned
end

function CAddonTemplateGameMode:SetWaveInterval( interval )
	local ent = GameRules:GetGameModeEntity()
	if interval <= 0 then
		ent:SetContextThink( "MCPLabWaves", nil, 0 )
		self.next_wave_time = nil
		print( "[MCP_LAB] waves stopped" )
		return
	end
	self.wave_number = self.wave_number or 0
	self.next_wave_time = GameRules:GetGameTime() + interval
	ent:SetContextThink( "MCPLabWaves", function()
		self.wave_number = self.wave_number + 1
		self:SpawnWave( self.wave_number, false )
		self.next_wave_time = GameRules:GetGameTime() + interval
		return interval
	end, interval )
	print( "[MCP_LAB] waves every " .. interval .. "s" )
end

function CAddonTemplateGameMode:ClearWaveUnits()
	for _, u in ipairs( self.wave_units or {} ) do
		if IsValidEntity( u ) then UTIL_Remove( u ) end
	end
	self.wave_units = {}
end

local function AvgDistance( units, point )
	local sum, n = 0, 0
	for _, u in ipairs( units ) do
		if IsValidEntity( u ) and u:IsAlive() then
			sum = sum + ( u:GetAbsOrigin() - point ):Length2D()
			n = n + 1
		end
	end
	return n > 0 and sum / n or 0
end

function CAddonTemplateGameMode:RunWaveTest( hero )
	local checks = {}
	-- Constants missing from the script_help2 dump: verify they exist at runtime
	print( string.format( "[MCP_LAB] constants: FIND_CLOSEST=%s FIND_UNITS_EVERYWHERE=%s DOTA_UNIT_ORDER_ATTACK_TARGET=%s",
		tostring( FIND_CLOSEST ), tostring( FIND_UNITS_EVERYWHERE ), tostring( DOTA_UNIT_ORDER_ATTACK_TARGET ) ) )

	-- Keep the hero alive while waves attack it
	hero:SetContextThink( "MCPLabKeepAlive", function()
		hero:SetHealth( hero:GetMaxHealth() )
		return self.wave_test_running and 0.5 or nil
	end, 0.5 )
	self.wave_test_running = true

	local units = self:SpawnWave( 1, true )
	checks.spawners = #units > 0
	for _, u in ipairs( units ) do
		local near = false
		for _, name in ipairs( WAVE_SPAWNERS ) do
			local s = Entities:FindByName( nil, name )
			if s and ( u:GetAbsOrigin() - s:GetAbsOrigin() ):Length2D() < 350 then near = true end
		end
		checks.spawners = checks.spawners and near
	end

	-- The custom AI must really be attached; default creature behaviour alone can also chase the hero
	local with_ai = 0
	for _, u in ipairs( units ) do if u:HasModifier( "modifier_mcp_wave_ai" ) then with_ai = with_ai + 1 end end
	checks.ai_attached = with_ai == #units

	local imps, giant = {}, nil
	for _, u in ipairs( units ) do
		if u:GetUnitName() == "npc_mcp_rift_giant" then giant = u else table.insert( imps, u ) end
	end
	local dist_start = AvgDistance( imps, hero:GetAbsOrigin() )
	local slam_before = GameRules.mcp_lab_slam_hits or 0

	hero:SetContextThink( "MCPLabWaveChase", function()
		checks.chase = AvgDistance( imps, hero:GetAbsOrigin() ) < dist_start - 300
		-- Bring the giant next to the hero so its AI must decide to slam
		FindClearSpaceForUnit( giant, hero:GetAbsOrigin() + Vector( 200, 0, 0 ), true )

		hero:SetContextThink( "MCPLabWaveSlam", function()
			checks.elite_slam = ( GameRules.mcp_lab_slam_hits or 0 ) > slam_before
			local waves_before = self.waves_spawned
			self:SetWaveInterval( 2 )

			hero:SetContextThink( "MCPLabWaveTimer", function()
				checks.timer = self.waves_spawned > waves_before
				self:SetWaveInterval( 0 )
				self.wave_test_running = false
				self:ClearWaveUnits()

				local all_ok, parts = true, {}
				for _, name in ipairs({ "spawners", "ai_attached", "chase", "elite_slam", "timer" }) do
					all_ok = all_ok and checks[name]
					table.insert( parts, name .. "=" .. tostring( checks[name] ) )
				end
				print( string.format( "[MCP_LAB] AUTOTEST stage3 %s: %s units=%d dist_start=%d", all_ok and "PASS" or "FAIL", table.concat( parts, " " ), #units, dist_start ) )
				self:RunItemTest( hero )
				return nil
			end, 2.6 )
			return nil
		end, 3.5 )
		return nil
	end, 3.0 )
end

--------------------------------------------------------------------------------
-- Stage 4: custom item with own icon — passive stats, active rift pull (motion controller), silence
--------------------------------------------------------------------------------

function CAddonTemplateGameMode:RunItemTest( hero )
	local checks = {}
	local armor_before = hero:GetPhysicalArmorValue( false )
	local item = hero:FindItemInInventory( "item_mcp_void_shard" ) or hero:AddItemByName( "item_mcp_void_shard" )
	checks.item_added = item ~= nil
	if not item then
		print( "[MCP_LAB] AUTOTEST stage4 FAIL: item not created" )
		return
	end
	checks.passive = hero:HasModifier( "modifier_item_mcp_void_shard" ) and hero:GetPhysicalArmorValue( false ) > armor_before

	local center = hero:GetAbsOrigin() + Vector( 500, 0, 0 )
	local dummies = {}
	for _, offset in ipairs({ Vector( 300, 0, 0 ), Vector( -250, 150, 0 ), Vector( 0, -300, 0 ) }) do
		local d = CreateUnitByName( "npc_dota_hero_target_dummy", center + offset, true, nil, nil, DOTA_TEAM_NEUTRALS )
		d:SetAbilityPoints( 0 )
		d:Hold()
		d:SetIdleAcquire( false )
		d:SetAcquisitionRange( 0 )
		d:AddNewModifier( d, nil, "modifier_mcp_damage_meter", {} )
		table.insert( dummies, d )
	end

	hero:SetContextThink( "MCPLabItemCast", function()
		item:EndCooldown()
		hero:GiveMana( 1000 )
		hero:CastAbilityOnPosition( center, item, hero:GetPlayerOwnerID() )

		hero:SetContextThink( "MCPLabItemCheck", function()
			local pulled, silenced, damaged = 0, 0, 0
			for _, d in ipairs( dummies ) do
				if ( d:GetAbsOrigin() - center ):Length2D() < 150 then pulled = pulled + 1 end
				if d:IsSilenced() then silenced = silenced + 1 end
				if DamageTaken( d ) > 0 then damaged = damaged + 1 end
			end
			checks.pull = pulled == #dummies
			checks.silence = silenced == #dummies
			checks.damage = damaged == #dummies

			local all_ok, parts = true, {}
			for _, name in ipairs({ "item_added", "passive", "pull", "silence", "damage" }) do
				all_ok = all_ok and checks[name]
				table.insert( parts, name .. "=" .. tostring( checks[name] ) )
			end
			print( string.format( "[MCP_LAB] AUTOTEST stage4 %s: %s pulled=%d silenced=%d", all_ok and "PASS" or "FAIL", table.concat( parts, " " ), pulled, silenced ) )
			return nil
		end, 1.6 )
		return nil
	end, 1.0 )
end
