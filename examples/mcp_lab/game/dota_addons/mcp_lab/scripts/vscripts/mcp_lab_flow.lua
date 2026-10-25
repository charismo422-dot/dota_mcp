-- Stage 11: game flow. Own lobby screen (GameSetup layout) where only the host changes the settings (lives, hero look),
-- the value travels JS -> Lua (host check on the server) -> net table -> every client; auto-pick, PreGameTime 0,
-- fixed 5 s respawn, a lives counter that ends the game, the hero on Roshan's model, a joke screen and own EndScreen.
-- Returns a table of methods that addon_game_mode.lua copies onto CAddonTemplateGameMode (see mcp_lab_hunters.lua).
local CAddonTemplateGameMode = {}

local NET_TABLE = "mcp_lab_flow"  -- declared in scripts/custom_net_tables.txt
local LIVES = { [3] = true, [5] = true, [10] = true, [0] = true }  -- 0 = infinite
local LOOKS = { mage = "", roshan = "models/creeps/roshan/roshan.vmdl" }  -- Roshan: attach_attack1 + ACT_DOTA_CAST_ABILITY_1..3 (inspect_model)
local DEFAULTS = { lives = 10, look = "mage" }
local RESPAWN_TIME = 5
local SETUP_TIME = 15  -- lobby countdown; the host may start earlier
local EF_NODRAW = 32   -- render effect flag (not in the script_help2 dump; checked live)

Convars:RegisterCommand( "mcp_lab_lobby_test", function()
	GameRules.AddonTemplate:RunLobbyTest()
end, "MCP Lab: stage 11 lobby part (run during the lobby screen): host flag, host-only change, value to Lua, start", 0 )

Convars:RegisterCommand( "mcp_lab_autotest11", function()
	local self = GameRules.AddonTemplate
	if self and self.hero then self:RunGameFlowTest( self.hero ) end
end, "MCP Lab: stage 11 autotest (lobby value, auto-pick, pre-game 0, respawn 5 s, lives, Roshan look, joke + end screen). Ends the game!", 0 )

Convars:RegisterCommand( "mcp_lab_gameover", function( _, how )
	GameRules.AddonTemplate:EndFlowGame( how == "win" )
end, "MCP Lab: end the game now to see the joke screen and the end screen (mcp_lab_gameover [win])", 0 )

Convars:RegisterCommand( "mcp_lab_lives", function( _, n )
	local self = GameRules.AddonTemplate
	self.lives_left = math.max( 0, tonumber( n ) or 3 )
	self.lives_infinite = tonumber( n ) == 0
	self:SendHudUpdate()
end, "MCP Lab: set the lives counter in game (mcp_lab_lives <n>, 0 = infinite)", 0 )

-- State changes are remembered with their time: the autotest proves hero selection / pre-game were skipped
if GameRules.mcp_lab_state_listener then StopListeningToGameEvent( GameRules.mcp_lab_state_listener ) end
GameRules.mcp_lab_state_listener = ListenToGameEvent( "game_rules_state_change", function()
	local self = GameRules.AddonTemplate
	if not self then return end
	self.state_log = self.state_log or {}
	table.insert( self.state_log, { state = GameRules:State_Get(), time = Time() } )
end, nil )

function CAddonTemplateGameMode:InitGameFlow()
	GameRules:SetCustomGameSetupAutoLaunchDelay( SETUP_TIME )
	GameRules:SetHeroSelectionTime( 0 )
	GameRules:SetStrategyTime( 0 )
	GameRules:SetShowcaseTime( 0 )
	GameRules:SetPreGameTime( 0 )
	GameRules:SetPostGameTime( 600 )  -- the end screen stays until the player leaves
	GameRules:GetGameModeEntity():SetFixedRespawnTime( RESPAWN_TIME )
	self.settings = { lives = DEFAULTS.lives, look = DEFAULTS.look }
	self.lobby_rejected, self.lobby_changes = 0, 0
	self.state_log = { { state = GameRules:State_Get(), time = Time() } }
	self:PublishSettings()
	CustomGameEventManager:RegisterListener( "mcp_lab_lobby_set", function( _, data ) self:OnLobbySet( data ) end )
	CustomGameEventManager:RegisterListener( "mcp_lab_lobby_ack", function( _, data ) self.lobby_ack = data end )
end

function CAddonTemplateGameMode:PublishSettings()
	CustomNetTables:SetTableValue( NET_TABLE, "lobby", { lives = self.settings.lives, look = self.settings.look, changes = self.lobby_changes } )
end

-- JS -> Lua. The client UI hides the buttons from non-hosts, but the server never trusts the client: the sender's
-- host privileges are checked here, and settings are frozen once the lobby is over.
function CAddonTemplateGameMode:OnLobbySet( data )
	local pid = tonumber( data.PlayerID ) or -1
	local player = PlayerResource:GetPlayer( pid )
	local key, value = tostring( data.key ), data.value
	local ok = player ~= nil and GameRules:PlayerHasCustomGameHostPrivileges( player )
		and GameRules:State_Get() == DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP
	if ok and key == "lives" then
		value = tonumber( value )
		ok = value ~= nil and LIVES[ value ] == true
	elseif ok and key == "look" then
		value = tostring( value )
		ok = LOOKS[ value ] ~= nil
	elseif ok then
		ok = false
	end
	if not ok then
		self.lobby_rejected = self.lobby_rejected + 1
		print( string.format( "[MCP_LAB] lobby: rejected %s=%s from player %d", key, tostring( data.value ), pid ) )
		return
	end
	self.settings[ key ] = value
	self.lobby_changes = self.lobby_changes + 1
	print( string.format( "[MCP_LAB] lobby: host set %s=%s", key, tostring( value ) ) )
	self:PublishSettings()
end

-- Called from OnNPCSpawned for the player's hero: the lobby is over, the settings are applied once
function CAddonTemplateGameMode:ApplyGameFlow( hero )
	self.lives_start = self.settings.lives
	self.lives_infinite = self.settings.lives == 0
	self.lives_left = self.settings.lives
	self.flow_deaths = 0
	self:ApplyLook( hero, self.settings.look )
	print( string.format( "[MCP_LAB] game flow: lives=%s look=%s", self.lives_infinite and "inf" or tostring( self.lives_left ), self.settings.look ) )
end

function CAddonTemplateGameMode:ApplyLook( hero, look )
	local model = LOOKS[ look ]
	if not model or model == "" then return end
	hero:SetOriginalModel( model )
	hero:SetModel( model )
	hero:SetModelScale( 0.6 )
	-- Cosmetics of the stock hero stay attached to the new model unless they are hidden
	local found, hidden = 0, 0
	for _, child in ipairs( hero:GetChildren() ) do
		if child:GetClassname() == "dota_item_wearable" then
			found = found + 1
			child:AddEffects( EF_NODRAW )
			hidden = hidden + 1
		end
	end
	self.look_wearables = { found = found, hidden = hidden }
end

function CAddonTemplateGameMode:OnFlowHeroDeath()
	if self.game_over or self.lives_left == nil then return end
	self.flow_deaths = ( self.flow_deaths or 0 ) + 1
	if self.lives_infinite then return end
	self.lives_left = math.max( 0, self.lives_left - 1 )
	if self.lives_left == 0 then
		self:EndFlowGame( false )
	end
end

-- Stats go into the net table BEFORE the winner is set: the EndScreen layout reads them when post-game starts
function CAddonTemplateGameMode:EndFlowGame( won )
	if self.game_over then return end
	self.game_over = true
	local stats = {
		won = won and 1 or 0,
		time = math.floor( GameRules:GetDOTATime( false, false ) ),
		lives_start = self.lives_start or self.settings.lives,
		deaths = self.flow_deaths or 0,
		creeps = self.hud_kills or 0,
		trophies = self.trophies or 0,
		killer = self.last_killer or "",
		look = self.settings.look,
		-- Server Lua stops in post-game (no thinks, listeners or console commands), so in an autotest the end screen
		-- presses its joke button by itself and prints its own check line from the client
		autotest = self.flow_test_running and 1 or 0,
	}
	self.end_stats = stats
	CustomNetTables:SetTableValue( NET_TABLE, "end", stats )
	print( string.format( "[MCP_LAB] game over: %s, deaths=%d", won and "victory" or "defeat", stats.deaths ) )
	GameRules:SetCustomVictoryMessage( " " )  -- the stock "Victory of the ..." banner would cover the joke window ("" = stock text)
	GameRules:SetCustomVictoryMessageDuration( 0 )
	GameRules:SetGameWinner( won and DOTA_TEAM_GOODGUYS or DOTA_TEAM_BADGUYS )
end

local function Sequence( steps )
	local i = 0
	local function next_step( delay )
		i = i + 1
		if not steps[i] then return end
		GameRules:GetGameModeEntity():SetContextThink( "MCPLab11Step" .. i, function()
			steps[i]( next_step )
			return nil
		end, delay or 0 )
	end
	next_step( 0 )
end

local function Kill( victim )
	ApplyDamage({ victim = victim, attacker = victim, damage = victim:GetHealth() + 1000, damage_type = DAMAGE_TYPE_PURE,
		damage_flags = DOTA_DAMAGE_FLAG_BYPASSES_INVULNERABILITY })
end

-- Lobby part: runs while the lobby screen is up. The JS answers a probe (host flag, buttons enabled, values shown),
-- then "clicks" lives = 3 and look = roshan through the same functions as the buttons; a request in the name of a
-- player without host privileges must be rejected; finally the JS presses Start.
function CAddonTemplateGameMode:RunLobbyTest()
	local r = { state = GameRules:State_Get() == DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP }
	self.lobby_test = r
	if not r.state then print( "[MCP_LAB] lobby test FAIL: not in the lobby (state " .. GameRules:State_Get() .. ")" ) return end
	local rejected_before = self.lobby_rejected
	GameRules:SetCustomGameSetupRemainingTime( -1 )  -- hold the lobby while the test runs
	Sequence({
		function( next )
			self.lobby_ack = nil
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_lobby_probe", { ping = 1 } )
			next( 0.5 )
		end,
		function( next )
			local ack = self.lobby_ack or {}
			r.js_host = ack.host == 1 and ack.buttons_enabled == 1
			r.js_default = tonumber( ack.lives ) == DEFAULTS.lives and ack.look == DEFAULTS.look
			-- player 7 does not exist in a one-player lobby -> no host privileges
			self:OnLobbySet( { PlayerID = 7, key = "lives", value = 5 } )
			-- the host itself sends an invalid value
			self:OnLobbySet( { PlayerID = 0, key = "lives", value = 4 } )
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_lobby_autochoose", { lives = 3, look = "roshan" } )
			next( 0.6 )
		end,
		function( next )
			r.nonhost_rejected = self.lobby_rejected == rejected_before + 2 and self.settings.lives ~= 5
			r.lua_value = self.settings.lives == 3 and self.settings.look == "roshan"
			local t = CustomNetTables:GetTableValue( NET_TABLE, "lobby" ) or {}
			r.net_table = tonumber( t.lives ) == 3 and t.look == "roshan"
			self.lobby_ack = nil
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_lobby_probe", { ping = 2 } )
			next( 0.5 )
		end,
		function( next )
			local ack = self.lobby_ack or {}
			r.js_shows = tonumber( ack.lives ) == 3 and ack.look == "roshan"
			local failed = {}
			for _, key in ipairs({ "state", "js_host", "js_default", "nonhost_rejected", "lua_value", "net_table", "js_shows" }) do
				if not r[ key ] then table.insert( failed, key ) end
			end
			r.failed = failed
			print( string.format( "[MCP_LAB] lobby test %s: checks=7 failed=[%s] rejected=%d", #failed == 0 and "PASS" or "FAIL",
				table.concat( failed, "," ), self.lobby_rejected - rejected_before ) )
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_lobby_start", {} )
		end,
	})
end

local function StateDuration( log, state )
	for i, e in ipairs( log ) do
		if e.state == state then
			local nxt = log[ i + 1 ]
			return nxt and ( nxt.time - e.time ) or ( Time() - e.time )
		end
	end
	return 0  -- state skipped completely
end

-- In-game part. Ends the game: relaunch the map before a repeat run.
function CAddonTemplateGameMode:RunGameFlowTest( hero )
	local r = {}
	local lt = self.lobby_test
	r.lobby = lt ~= nil and #( lt.failed or { "not run" } ) == 0
	r.lives_from_lobby = self.lives_start == 3
	r.autopick = hero:GetUnitName() == "npc_dota_hero_crystal_maiden" and PlayerResource:GetSelectedHeroEntity( 0 ) == hero
		and StateDuration( self.state_log, DOTA_GAMERULES_STATE_HERO_SELECTION ) < 1.5
	r.pregame = GameRules:State_Get() == DOTA_GAMERULES_STATE_GAME_IN_PROGRESS
		and StateDuration( self.state_log, DOTA_GAMERULES_STATE_PRE_GAME ) < 1.5
	local w = self.look_wearables or { found = -1, hidden = -2 }
	r.look = hero:GetModelName() == LOOKS.roshan and w.found == w.hidden
	r.respawn_setting = GameRules:GetGameModeEntity():GetFixedRespawnTime() == RESPAWN_TIME
	local hud_ping, respawn_left
	local function hud_lives( ping )
		local ack = self.hud_acks[ tostring( ping ) ]
		return type( ack ) == "table" and tostring( ack.lives ) or "-"
	end
	Sequence({
		function( next )
			hud_ping = 1101
			self:SendHudUpdate( hud_ping )
			next( 0.5 )
		end,
		function( next )
			r.hud_start = hud_lives( hud_ping ) == "3"
			hero:RemoveModifierByName( "modifier_invulnerable" )
			Kill( hero )
			next( 0.3 )
		end,
		function( next )
			respawn_left = hero:GetTimeUntilRespawn()
			r.respawn_timer = not hero:IsAlive() and respawn_left > RESPAWN_TIME - 0.6 and respawn_left <= RESPAWN_TIME
			r.lives_down = self.lives_left == 2
			hud_ping = 1102
			self:SendHudUpdate( hud_ping )
			next( RESPAWN_TIME )
		end,
		function( next )
			r.respawned = hero:IsAlive()
			r.hud_lives = hud_lives( hud_ping ) == "2"
			Kill( hero )
			next( 0.3 )
		end,
		function()
			hero:RespawnHero( false, false )
			-- Third death: the counter reaches 0 and the game ends inside this call. Server Lua stops in post-game,
			-- so the server part is checked right here; the end screen prints its own check line from the client.
			self.flow_test_running = true
			Kill( hero )
			self.flow_test_running = false
			r.game_over = self.game_over == true and self.lives_left == 0
			local t = CustomNetTables:GetTableValue( NET_TABLE, "end" ) or {}
			r.end_table = tonumber( t.deaths ) == 3 and tonumber( t.lives_start ) == 3 and tonumber( t.won ) == 0 and tonumber( t.autotest ) == 1
			local failed = {}
			for _, key in ipairs({ "lobby", "lives_from_lobby", "autopick", "pregame", "look", "respawn_setting", "hud_start",
				"respawn_timer", "lives_down", "respawned", "hud_lives", "game_over", "end_table" }) do
				if not r[ key ] then table.insert( failed, key ) end
			end
			print( string.format( "[MCP_LAB] AUTOTEST stage11 server %s: checks=13 failed=[%s] respawn_left=%.2f wearables=%d/%d hero_select=%.2f pregame=%.2f state=%d (end screen line follows from the client)",
				#failed == 0 and "PASS" or "FAIL", table.concat( failed, "," ), respawn_left or -1, w.hidden, w.found,
				StateDuration( self.state_log, DOTA_GAMERULES_STATE_HERO_SELECTION ), StateDuration( self.state_log, DOTA_GAMERULES_STATE_PRE_GAME ),
				GameRules:State_Get() ) )
		end,
	})
end

return CAddonTemplateGameMode
