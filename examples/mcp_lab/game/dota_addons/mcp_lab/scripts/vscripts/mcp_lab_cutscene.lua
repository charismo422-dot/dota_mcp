-- Stage 10: a ~40 s cutscene "The Rift Awakens". Lua owns the timeline and the camera (the camera follows an
-- invisible thinker moved every frame), Panorama (mcp_lab_cutscene.*) hides the stock HUD and draws letterbox
-- bars, full-screen slides with zoom-in and shake, subtitles and the hold-to-skip ring.
-- Returns a table of methods that addon_game_mode.lua copies onto CAddonTemplateGameMode (see mcp_lab_hunters.lua).
local CAddonTemplateGameMode = {}

local THEME, BOOM = "MCP_Lab.CutsceneTheme", "MCP_Lab.CutsceneBoom"  -- .wav (40 s) and .mp3 compiled directly
-- Shot start times must match SHOT_TIMES in tools/make_lab_cutscene.py (bells in the theme)
local SHOTS = {
	{ t = 0, slide = "", sub = "#mcp_lab_cut_sub1" },          -- world: camera flies from the hero to the rift
	{ t = 7, slide = "rift", sub = "#mcp_lab_cut_sub2" },
	{ t = 16, slide = "mage", sub = "#mcp_lab_cut_sub3" },
	{ t = 24, slide = "hunters", sub = "#mcp_lab_cut_sub4", boom = true },
	{ t = 33, slide = "", sub = "#mcp_lab_cut_sub5" },         -- world: camera flies back to the hero
}
local SHAKES = { { t = 9, power = 10 }, { t = 24, power = 30 }, { t = 27.5, power = 12 } }
local FLY_OUT, FLY_BACK = { 1, 6 }, { 33, 39 }
local DIST_CLOSE, DIST_WIDE, DIST_DEFAULT = 900, 1600, 1134  -- stock camera distance is 1134
local TICK = 1 / 30

Convars:RegisterCommand( "mcp_lab_cutscene", function( _, start_at )
	local self = GameRules.AddonTemplate
	if self and self.hero then self:StartCutscene( self.hero, tonumber( start_at ) or 0 ) end
end, "MCP Lab: play the stage 10 cutscene (mcp_lab_cutscene [start second]); hold SPACE or the left mouse button 1 s to skip", 0 )

Convars:RegisterCommand( "mcp_lab_autotest10", function()
	local self = GameRules.AddonTemplate
	if self and self.hero then self:RunCutsceneTest( self.hero ) end
end, "MCP Lab: stage 10 autotest (cutscene: camera, HUD, invulnerability, slides, sound, skip)", 0 )

local function Smooth( a, b, t )
	t = math.max( 0, math.min( 1, t ) )
	return a + ( b - a ) * t * t * ( 3 - 2 * t )
end

local function RiftPoint( hero )
	local ent = Entities:FindByName( nil, "lab_spawn_east" )
	return ent and ent:GetAbsOrigin() or hero:GetAbsOrigin() + Vector( 1200, 0, 0 )
end

function CAddonTemplateGameMode:RegisterCutsceneListeners()
	CustomGameEventManager:RegisterListener( "mcp_lab_cut_skip", function( _, data )
		-- the client reports how long the key was held; the server still checks it
		if self.cutscene and tonumber( data.held or 0 ) >= 1.0 then self:EndCutscene( "skip" ) end
	end )
	CustomGameEventManager:RegisterListener( "mcp_lab_cut_ack", function( _, data )
		self.cut_acks = self.cut_acks or {}
		self.cut_acks[ tostring( data.ping ) ] = data
	end )
end

function CAddonTemplateGameMode:StartCutscene( hero, start_at )
	if self.cutscene then self:EndCutscene( "restart" ) end
	local pid = hero:GetPlayerOwnerID()
	local duration = hero:GetSoundDuration( THEME, "" )
	if duration <= 0 then duration = 40 end  -- audio not loaded: keep the timeline anyway
	local home, rift = hero:GetAbsOrigin(), RiftPoint( hero )
	local cam = CreateModifierThinker( hero, nil, "modifier_mcp_cutscene_camera", {}, home, hero:GetTeamNumber(), false )
	local cs = { hero = hero, pid = pid, cam = cam, home = home, rift = rift, duration = duration,
		start = GameRules:GetGameTime() - ( start_at or 0 ), next_shot = 1, next_shake = 1, boom = false }
	self.cutscene = cs
	hero:Stop()
	hero:AddNewModifier( hero, nil, "modifier_mcp_cutscene", {} )
	AddFOWViewer( hero:GetTeamNumber(), rift, 1200, duration + 1, false )
	PlayerResource:SetCameraTarget( pid, cam )
	EmitGlobalSound( THEME )
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_start", { duration = duration } )
	-- skip the shots and shakes that are already behind start_at
	while SHOTS[ cs.next_shot + 1 ] and SHOTS[ cs.next_shot + 1 ].t <= ( start_at or 0 ) do cs.next_shot = cs.next_shot + 1 end
	while SHAKES[ cs.next_shake ] and SHAKES[ cs.next_shake ].t < ( start_at or 0 ) do cs.next_shake = cs.next_shake + 1 end
	GameRules:GetGameModeEntity():SetContextThink( "MCPLabCutscene", function()
		return self:CutsceneTick()
	end, 0 )
	print( string.format( "[MCP_LAB] cutscene started at %.0f s, length %.2f s (theme duration from GetSoundDuration)", start_at or 0, duration ) )
end

function CAddonTemplateGameMode:CutsceneTick()
	local cs = self.cutscene
	if not cs then return nil end
	local t = GameRules:GetGameTime() - cs.start
	if t >= cs.duration then
		self:EndCutscene( "end" )
		return nil
	end
	local shot = SHOTS[ cs.next_shot ]
	if shot and t >= shot.t then
		cs.next_shot = cs.next_shot + 1
		cs.slide = shot.slide
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_shot", { index = cs.next_shot - 1, slide = shot.slide, sub = shot.sub } )
		if shot.boom then EmitGlobalSound( BOOM ); cs.boom = true end
		if cs.next_shot - 1 == 1 then
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_camera", { from = DIST_CLOSE, to = DIST_WIDE, time = FLY_OUT[2] - FLY_OUT[1] } )
		elseif shot.t == FLY_BACK[1] then
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_camera", { from = DIST_WIDE, to = DIST_DEFAULT, time = FLY_BACK[2] - FLY_BACK[1] } )
		end
	end
	local shake = SHAKES[ cs.next_shake ]
	if shake and t >= shake.t then
		cs.next_shake = cs.next_shake + 1
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_shake", { power = shake.power } )
	end
	-- camera path: hold on the hero, fly to the rift, stay there behind the slides, fly back
	local pos
	if t < FLY_BACK[1] then
		pos = cs.home + ( cs.rift - cs.home ) * Smooth( 0, 1, ( t - FLY_OUT[1] ) / ( FLY_OUT[2] - FLY_OUT[1] ) )
	else
		pos = cs.rift + ( cs.hero:GetAbsOrigin() - cs.rift ) * Smooth( 0, 1, ( t - FLY_BACK[1] ) / ( FLY_BACK[2] - FLY_BACK[1] ) )
	end
	if IsValidEntity( cs.cam ) then cs.cam:SetAbsOrigin( pos ) end
	return TICK
end

function CAddonTemplateGameMode:EndCutscene( reason )
	local cs = self.cutscene
	if not cs then return end
	self.cutscene = nil
	GameRules:GetGameModeEntity():SetContextThink( "MCPLabCutscene", nil, 0 )
	StopGlobalSound( THEME )
	StopGlobalSound( BOOM )
	PlayerResource:SetCameraTarget( cs.pid, nil )
	if IsValidEntity( cs.hero ) then
		cs.hero:RemoveModifierByName( "modifier_mcp_cutscene" )
		CenterCameraOnUnit( cs.pid, cs.hero )
	end
	if IsValidEntity( cs.cam ) then UTIL_Remove( cs.cam ) end
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_end", { reason = reason } )
	self.cutscene_last = { reason = reason, at = GameRules:GetGameTime() - cs.start, boom = cs.boom }
	print( string.format( "[MCP_LAB] cutscene ended: %s at %.1f s", reason, self.cutscene_last.at ) )
end

-- Runs steps one after another; each step calls next( delay ). Unique think names (see LESSONS stage 9).
local function Sequence( steps )
	local i = 0
	local function next_step( delay )
		i = i + 1
		if not steps[i] then return end
		GameRules:GetGameModeEntity():SetContextThink( "MCPLab10Step" .. i, function()
			steps[i]( next_step )
			return nil
		end, delay or 0 )
	end
	next_step( 0 )
end

-- Stage 10 autotest: run A plays to the hunters slide and is skipped by a simulated 1.1 s hold (a 0.5 s hold
-- must not skip); run B starts at 32 s and ends by itself, checking the camera flight back and the restore.
function CAddonTemplateGameMode:RunCutsceneTest( hero )
	local r, pings = {}, 0
	local function check( name, pass, info )
		r[ #r + 1 ] = pass
		print( string.format( "[MCP_LAB] AUTOTEST10 %s %s%s", name, pass and "PASS" or "FAIL", info and ( " (" .. info .. ")" ) or "" ) )
	end
	local function probe()
		pings = pings + 1
		CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_probe", { ping = pings } )
		return tostring( pings )
	end
	local function ack( p ) return ( self.cut_acks or {} )[ p ] or {} end
	local function near( a, x, y, radius )
		return a.cam_x and ( Vector( a.cam_x, a.cam_y, 0 ) - Vector( x, y, 0 ) ):Length2D() < radius, a.cam_x and string.format( "camera %.0f %.0f", a.cam_x, a.cam_y ) or "no reply"
	end
	if self.cutscene then self:EndCutscene( "restart" ) end
	self.cutscene_last = nil
	hero:RemoveModifierByName( "modifier_fountain_invulnerability" )
	local home, rift = hero:GetAbsOrigin(), RiftPoint( hero )
	local p, hp
	Sequence({
		function( n ) p = probe(); n( 0.4 ) end,
		function( n )
			local a = ack( p )
			check( "hud visible before", a.hud_visible == 1, "found=" .. tostring( a.hud_found ) )
			local theme, boom, none = hero:GetSoundDuration( THEME, "" ), hero:GetSoundDuration( BOOM, "" ), hero:GetSoundDuration( "MCP_Lab.NoSuchCutscene", "" )
			check( "wav theme ~40 s", theme > 38 and theme < 42, string.format( "%.3f", theme ) )
			check( "mp3 compiled and loaded", boom > 1.5 and boom < 3, string.format( "%.3f", boom ) )
			check( "unknown sound", none <= 0, string.format( "%.3f", none ) )
			self:StartCutscene( hero, 0 )
			n( 0.6 )
		end,
		function( n )
			check( "invulnerable modifier", hero:HasModifier( "modifier_mcp_cutscene" ) and hero:IsInvulnerable() )
			hp = hero:GetHealth()
			ApplyDamage({ victim = hero, attacker = hero, damage = 300, damage_type = DAMAGE_TYPE_PURE })
			hero:MoveToPosition( home + Vector( 600, 0, 0 ) )
			p = probe()
			n( 0.6 )
		end,
		function( n )
			local a = ack( p )
			check( "no damage taken", hero:GetHealth() >= hp, hp .. " -> " .. hero:GetHealth() )
			check( "orders ignored", ( hero:GetAbsOrigin() - home ):Length2D() < 20 )
			check( "stock hud + other custom layouts hidden", a.hud_visible == 0 and a.hidden == 3 and a.overlay == 1 and a.bars == 1, "hidden=" .. tostring( a.hidden ) )
			check( "subtitle 1", a.sub == "#mcp_lab_cut_sub1" and ( a.sub_len or 0 ) > 0, "chars=" .. tostring( a.sub_len ) )
			n( 6.6 - 1.6 )
		end,
		function( n ) p = probe(); n( 0.3 ) end,
		function( n )
			local pass, info = near( ack( p ), rift.x, rift.y, 350 )
			check( "camera flew to the rift", pass, info )
			n( 9.6 - 6.9 )
		end,
		function( n ) p = probe(); n( 0.3 ) end,
		function( n )
			local a = ack( p )
			check( "slide rift shown", a.slide == "rift" and a.slide_opacity == 1, "slide=" .. tostring( a.slide ) )
			check( "zoom-in running", ( a.zoom or 0 ) > 1.01, string.format( "scale %.3f", a.zoom or 0 ) )
			check( "shake running", ( a.shake or 0 ) > 0, string.format( "offset %.1f", a.shake or 0 ) )
			n( 16.6 - 9.9 )
		end,
		function( n ) p = probe(); n( 0.3 ) end,
		function( n )
			local a = ack( p )
			check( "slide mage + subtitle 3", a.slide == "mage" and a.sub == "#mcp_lab_cut_sub3" )
			n( 24.6 - 16.9 )
		end,
		function( n ) p = probe(); n( 0.3 ) end,
		function( n )
			local a = ack( p )
			check( "slide hunters + boom", a.slide == "hunters" and self.cutscene and self.cutscene.boom )
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_autohold", { seconds = 0.5 } )
			n( 1.0 )
		end,
		function( n )
			check( "short hold does not skip", self.cutscene ~= nil )
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_cut_autohold", { seconds = 1.3 } )
			n( 1.6 )
		end,
		function( n )
			local last = self.cutscene_last or {}
			check( "1 s hold skips", last.reason == "skip", string.format( "at %.1f s", last.at or -1 ) )
			p = probe()
			n( 0.6 )
		end,
		function( n )
			local a = ack( p )
			check( "hud restored after skip", a.hud_visible == 1 and a.overlay == 0 )
			check( "invulnerability removed", not hero:HasModifier( "modifier_mcp_cutscene" ) and not hero:IsInvulnerable() )
			local pass, info = near( a, hero:GetAbsOrigin().x, hero:GetAbsOrigin().y, 400 )
			check( "camera back on the hero after skip", pass, info )
			self:StartCutscene( hero, 32 )
			n( 3.5 )
		end,
		function( n ) p = probe(); n( 0.3 ) end,
		function( n )
			local a = ack( p )
			check( "world shot 5, overlay without slide", a.slide == "" and a.sub == "#mcp_lab_cut_sub5" and a.hud_visible == 0 )
			n( 40.5 - 35.8 )
		end,
		function( n )
			local last = self.cutscene_last or {}
			check( "ends by itself at theme length", last.reason == "end" and math.abs( ( last.at or 0 ) - hero:GetSoundDuration( THEME, "" ) ) < 0.2, string.format( "at %.2f s", last.at or -1 ) )
			p = probe()
			n( 0.4 )
		end,
		function()
			local a = ack( p )
			check( "hud restored after end", a.hud_visible == 1 and a.overlay == 0 and a.distance == DIST_DEFAULT, "distance=" .. tostring( a.distance ) )
			local pass, info = near( a, hero:GetAbsOrigin().x, hero:GetAbsOrigin().y, 400 )
			check( "camera back on the hero after end", pass, info )
			local ok, total = 0, #r
			for _, v in ipairs( r ) do if v then ok = ok + 1 end end
			print( string.format( "[MCP_LAB] AUTOTEST10 %s %d/%d", ok == total and "PASS" or "FAIL", ok, total ) )
		end,
	})
end

return CAddonTemplateGameMode
