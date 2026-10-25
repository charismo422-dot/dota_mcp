-- Stage 9: enemy stock heroes under Lua AI ("hunters"), a phased boss, own currency (trophies),
-- tracking of the player's killer and hunters' power that grows by timer and when a hunter falls.
-- addon_game_mode.lua runs in its own script scope, so its globals (the game mode class) are not visible here:
-- this file returns a table of methods that addon_game_mode.lua copies onto CAddonTemplateGameMode.
local CAddonTemplateGameMode = {}

local HUNTERS = { "npc_dota_hero_sven", "npc_dota_hero_lina" }
local BOSS = "npc_dota_hero_axe"
-- Stock names from get_base_dota_definition (abilities from the hero KV, items from the stock bot loadouts)
local SKILLS = {
	npc_dota_hero_sven = { "sven_storm_bolt", "sven_warcry" },
	npc_dota_hero_lina = { "lina_light_strike_array", "lina_dragon_slave" },
	npc_dota_hero_axe = { "axe_berserkers_call", "axe_battle_hunger", "axe_counter_helix" },
}
local ITEMS = { npc_dota_hero_sven = "item_power_treads", npc_dota_hero_lina = "item_arcane_boots", npc_dota_hero_axe = "item_heart" }
local TROPHIES = { hunter = 5, boss = 25 }

local function DamageTaken( unit )
	local meter = unit:FindModifierByName( "modifier_mcp_damage_meter" )
	return meter and meter.total or 0
end

Convars:RegisterCommand( "mcp_lab_hunters", function( _, level )
	GameRules.AddonTemplate:StartHunterDemo( tonumber( level ) or 3 )
end, "MCP Lab: two enemy hero hunters at the spawners (mcp_lab_hunters <level>, 0 = remove all)", 0 )

Convars:RegisterCommand( "mcp_lab_boss", function( _, level )
	GameRules.AddonTemplate:StartBossDemo( tonumber( level ) or 6 )
end, "MCP Lab: phased boss at the east spawner, runs to the west spawner in phase 3", 0 )

Convars:RegisterCommand( "mcp_lab_autotest9", function()
	GameRules.AddonTemplate:RunEnemyHeroTest( GameRules.AddonTemplate.hero )
end, "MCP Lab: stage 9 autotest (hunter AI, retreat, killer, trophies, power, boss phases)", 0 )

function CAddonTemplateGameMode:SpawnEnemyHero( name, pos, level )
	local hero = CreateUnitByName( name, pos, true, nil, nil, DOTA_TEAM_BADGUYS )
	if not hero then
		print( "[MCP_LAB] enemy hero not created: " .. name )
		return nil
	end
	for _ = 2, level do hero:HeroLevelUp( false ) end
	hero:SetAbilityPoints( 0 )
	for _, ab_name in ipairs( SKILLS[ name ] or {} ) do
		local ab = hero:FindAbilityByName( ab_name )
		if ab then ab:SetLevel( level >= 6 and 2 or 1 ) end
	end
	hero:AddItemByName( ITEMS[ name ] )
	hero:SetRespawnsDisabled( true )  -- no player owner: a dead hunter is removed, not respawned
	hero:AddNewModifier( hero, nil, "modifier_mcp_damage_meter", {} )
	self.enemy_heroes = self.enemy_heroes or {}
	table.insert( self.enemy_heroes, hero )
	return hero
end

-- spots[i] = { pos = Vector, home = Vector } for HUNTERS[i]; home is where the hunter retreats to
function CAddonTemplateGameMode:SpawnHunters( spots, level )
	local spawned = {}
	for i, name in ipairs( HUNTERS ) do
		local spot = spots[i]
		local h = spot and self:SpawnEnemyHero( name, spot.pos, level )
		if h then
			h.mcp_role = "hunter"
			h:AddNewModifier( h, nil, "modifier_mcp_hunter_ai", { home_x = spot.home.x, home_y = spot.home.y } )
			h:AddNewModifier( h, nil, "modifier_mcp_hunter_power", {} ):SetStackCount( self.hunter_power or 0 )
			table.insert( spawned, h )
		end
	end
	return spawned
end

function CAddonTemplateGameMode:SpawnBoss( pos, level, run_point )
	local boss = self:SpawnEnemyHero( BOSS, pos, level )
	if not boss then return nil end
	boss.mcp_role = "boss"
	boss:SetRenderColor( 255, 110, 110 )
	boss:AddNewModifier( boss, nil, "modifier_mcp_boss_ai", { run_x = run_point.x, run_y = run_point.y } )
	self.boss = boss
	return boss
end

function CAddonTemplateGameMode:RaiseHunterPower( reason )
	self.hunter_power = ( self.hunter_power or 0 ) + 1
	self.power_raises = self.power_raises or {}
	self.power_raises[ reason ] = ( self.power_raises[ reason ] or 0 ) + 1
	for _, h in ipairs( self.enemy_heroes or {} ) do
		local m = IsValidEntity( h ) and h:IsAlive() and h:FindModifierByName( "modifier_mcp_hunter_power" )
		if m then m:SetStackCount( self.hunter_power ) end
	end
	self:SendHudUpdate()
end

function CAddonTemplateGameMode:SetHunterPowerInterval( interval )
	local ent = GameRules:GetGameModeEntity()
	if interval <= 0 then
		ent:SetContextThink( "MCPLabHunterPower", nil, 0 )
		return
	end
	ent:SetContextThink( "MCPLabHunterPower", function()
		self:RaiseHunterPower( "timer" )
		return interval
	end, interval )
end

function CAddonTemplateGameMode:ClearEnemyHeroes()
	self:SetHunterPowerInterval( 0 )
	for _, h in ipairs( self.enemy_heroes or {} ) do
		if IsValidEntity( h ) then UTIL_Remove( h ) end
	end
	self.enemy_heroes, self.boss = {}, nil
end

-- Called from OnEntityKilled for units with mcp_role
function CAddonTemplateGameMode:OnEnemyHeroKilled( unit, attacker )
	if attacker and attacker:GetTeamNumber() == DOTA_TEAM_GOODGUYS then
		self.trophies = ( self.trophies or 0 ) + TROPHIES[ unit.mcp_role ]
	end
	if unit.mcp_role == "hunter" then self:RaiseHunterPower( "event" ) end  -- survivors grow stronger
	if unit == self.boss then self.boss = nil end
	GameRules:GetGameModeEntity():SetContextThink( "MCPLabRemove" .. unit:entindex(), function()
		if IsValidEntity( unit ) then UTIL_Remove( unit ) end
		return nil
	end, 3 )
	self:SendHudUpdate()
end

function CAddonTemplateGameMode:OnPlayerHeroKilled( attacker )
	self.player_deaths = ( self.player_deaths or 0 ) + 1
	self.last_killer = attacker and IsValidEntity( attacker ) and attacker:GetUnitName() or "unknown"
	print( "[MCP_LAB] player hero killed by " .. self.last_killer )
	self:SendHudUpdate()
end

local function SpawnerOrigin( name, fallback )
	local ent = Entities:FindByName( nil, name )
	return ent and ent:GetAbsOrigin() or fallback
end

function CAddonTemplateGameMode:StartHunterDemo( level )
	self:ClearEnemyHeroes()
	if level <= 0 then
		print( "[MCP_LAB] hunters removed" )
		return
	end
	local west = SpawnerOrigin( "lab_spawn_west", Vector( -1000, 0, 128 ) )
	local east = SpawnerOrigin( "lab_spawn_east", Vector( 1000, 0, 128 ) )
	self:SpawnHunters( { { pos = west, home = west }, { pos = east, home = east } }, level )
	self:SetHunterPowerInterval( 30 )
	print( "[MCP_LAB] hunters spawned, level " .. level .. ", power +1 every 30 s" )
end

function CAddonTemplateGameMode:StartBossDemo( level )
	local east = SpawnerOrigin( "lab_spawn_east", Vector( 1000, 0, 128 ) )
	local west = SpawnerOrigin( "lab_spawn_west", Vector( -1000, 0, 128 ) )
	if IsValidEntity( self.boss ) then UTIL_Remove( self.boss ) end
	self:SpawnBoss( east, level, west )
	print( "[MCP_LAB] boss spawned, level " .. level )
end

-- Runs fn(next) steps one after another; each step calls next( delay ) to schedule the following one
local function Sequence( steps )
	local i = 0
	local function next_step( delay )
		i = i + 1
		if not steps[i] then return end
		GameRules:GetGameModeEntity():SetContextThink( "MCPLab9Step" .. i, function()
			steps[i]( next_step )
			return nil
		end, delay or 0 )
	end
	next_step( 0 )
end

local function Kill( victim, attacker )
	ApplyDamage({ victim = victim, attacker = attacker, damage = victim:GetHealth() + 1000, damage_type = DAMAGE_TYPE_PURE })
end

-- Stage 9 autotest. The player's hero is invulnerable while the AI is checked, so the hunters pick the
-- training dummies (closest enemy heroes); the hero is then killed by a hunter on purpose to test killer tracking.
function CAddonTemplateGameMode:RunEnemyHeroTest( hero )
	self:ClearEnemyHeroes()
	self.trophies, self.hunter_power, self.power_raises = 0, 0, {}
	local r = {}
	local base = hero:GetAbsOrigin()
	local center = base + Vector( 0, 400, 0 )
	hero:AddNewModifier( hero, nil, "modifier_invulnerable", { duration = 7 } )
	local dummies = self:SpawnTargets( center )
	local hunters = self:SpawnHunters( {
		{ pos = center + Vector( -300, 300, 0 ), home = center + Vector( -800, 600, 0 ) },
		{ pos = center + Vector( 300, 300, 0 ), home = center + Vector( 800, 600, 0 ) },
	}, 6 )
	local sven, lina = hunters[1], hunters[2]
	if not sven or not lina then print( "[MCP_LAB] AUTOTEST stage9 FAIL: hunters not spawned" ) return end
	local sven_ai = sven:FindModifierByName( "modifier_mcp_hunter_ai" )
	local lina_ai = lina:FindModifierByName( "modifier_mcp_hunter_ai" )
	self:SetHunterPowerInterval( 2 )
	local boss, boss_ai, deaths_before, power_before, dist_before, hud_ping

	local function count( t ) local n = 0 for _, v in pairs( t ) do n = n + v end return n end
	local function dummy_damage() local d = 0 for _, u in ipairs( dummies ) do d = d + DamageTaken( u ) end return d end
	local function note_gap( log, from, to )
		local a, b
		for _, e in ipairs( log ) do
			if e.what == from then a = e.time end
			if e.what == to then b = e.time end
		end
		return ( a and b ) and ( b - a ) or -1
	end

	Sequence({
		function( next ) next( 4 ) end,
		function( next )
			r.level = sven:GetLevel() == 6 and lina:GetLevel() == 6
			r.items = sven:HasItemInInventory( "item_power_treads" ) and lina:HasItemInInventory( "item_arcane_boots" )
			r.casts = count( sven_ai.casts ) >= 1 and count( lina_ai.casts ) >= 1
			r.dummy_hit = dummy_damage() > 0
			r.power_timer = ( self.power_raises.timer or 0 ) >= 1 and lina:FindModifierByName( "modifier_mcp_hunter_power" ):GetStackCount() == self.hunter_power
			print( string.format( "[MCP_LAB] stage9 casts sven=%d lina=%d dummy_damage=%d power=%d",
				count( sven_ai.casts ), count( lina_ai.casts ), dummy_damage(), self.hunter_power ) )
			dist_before = ( sven:GetAbsOrigin() - center ):Length2D()
			sven:SetHealth( sven:GetMaxHealth() * 0.2 )
			next( 1.5 )
		end,
		function( next )
			r.retreat = sven_ai.state == "retreat" and sven_ai.retreats == 1 and ( sven:GetAbsOrigin() - center ):Length2D() > dist_before + 100
			sven:SetHealth( sven:GetMaxHealth() )
			next( 1 )
		end,
		function( next )
			r.came_back = sven_ai.state == "hunt" and sven_ai.returns == 1
			self:SetHunterPowerInterval( 0 )
			power_before = self.hunter_power
			deaths_before = self.player_deaths or 0
			hero:RemoveModifierByName( "modifier_invulnerable" )
			Kill( hero, lina )
			next( 0.5 )
		end,
		function( next )
			r.killer = self.player_deaths == deaths_before + 1 and self.last_killer == "npc_dota_hero_lina"
			hero:RespawnHero( false, false )
			hero:AddNewModifier( hero, nil, "modifier_invulnerable", { duration = 30 } )
			Kill( sven, hero )
			next( 0.5 )
		end,
		function( next )
			r.trophy_hunter = self.trophies == TROPHIES.hunter
			r.power_event = self.hunter_power == power_before + 1 and self.power_raises.event == 1
				and lina:FindModifierByName( "modifier_mcp_hunter_power" ):GetStackCount() == power_before + 1
			boss = self:SpawnBoss( center + Vector( 0, -200, 0 ), 10, center + Vector( 700, -200, 0 ) )
			boss_ai = boss:FindModifierByName( "modifier_mcp_boss_ai" )
			next( 0.5 )
		end,
		function( next )
			ApplyDamage({ victim = boss, attacker = hero, damage = boss:GetMaxHealth() * 0.45, damage_type = DAMAGE_TYPE_PURE })
			next( 0.4 )
		end,
		function( next )
			r.telegraph = boss_ai.state == "telegraph" and boss:HasModifier( "modifier_mcp_boss_telegraph" ) and boss_ai.call:IsCooldownReady()
			next( 1.6 )
		end,
		function( next )
			local gap = note_gap( boss_ai.log, "telegraph2", "phase2" )
			r.phase2 = boss_ai.phase == 2 and not boss_ai.call:IsCooldownReady() and gap >= 0.95 and gap <= 1.2
			Kill( boss, hero )
			r.min_health = boss:IsAlive() and boss:GetHealth() == 1
			next( 1.5 )
		end,
		function( next )
			local gap = note_gap( boss_ai.log, "telegraph3", "phase3" )
			r.phase3_run = boss_ai.phase == 3 and ( boss_ai.state == "run" or boss_ai.mortal ) and gap >= 0.95 and gap <= 1.2
			next( 4 )
		end,
		function( next )
			r.arrived = boss_ai.mortal == true and ( boss:GetAbsOrigin() - boss_ai.run_point ):Length2D() <= 150
			Kill( boss, hero )
			next( 0.5 )
		end,
		function( next )
			r.boss_dead = not boss:IsAlive()
			r.trophy_boss = self.trophies == TROPHIES.hunter + TROPHIES.boss
			hud_ping = RandomInt( 1000, 999999 )
			self:SendHudUpdate( hud_ping )
			next( 1 )
		end,
		function( next )
			local ack = self.hud_acks[ tostring( hud_ping ) ]
			r.hud = type( ack ) == "table" and tonumber( ack.trophies ) == self.trophies and ack.killer ~= ""
			local failed = {}
			for _, key in ipairs({ "level", "items", "casts", "dummy_hit", "power_timer", "retreat", "came_back", "killer", "trophy_hunter",
				"power_event", "telegraph", "phase2", "min_health", "phase3_run", "arrived", "boss_dead", "trophy_boss", "hud" }) do
				if not r[ key ] then table.insert( failed, key ) end
			end
			print( string.format( "[MCP_LAB] AUTOTEST stage9 %s: checks=18 failed=[%s] trophies=%d killer=%s hud_killer=%s",
				#failed == 0 and "PASS" or "FAIL", table.concat( failed, "," ), self.trophies, tostring( self.last_killer ),
				type( ack ) == "table" and tostring( ack.killer ) or "-" ) )
			self:ClearEnemyHeroes()
			for _, u in ipairs( dummies ) do if IsValidEntity( u ) then UTIL_Remove( u ) end end
			hero:RemoveModifierByName( "modifier_invulnerable" )
		end,
	})
end

return CAddonTemplateGameMode
