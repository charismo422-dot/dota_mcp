-- Stage 12: checks for "mode 1" (neutral names, no story). Part 1: the stock dota.vmap copied into the addon
-- (prepare_map_from_template source_template="dota" -> maps/m1_dota.vmap), compiled and launched.

Convars:RegisterCommand( "mcp_lab_autotest12_map", function()
	local towers = #Entities:FindAllByClassname( "npc_dota_tower" )
	local ancients = #Entities:FindAllByClassname( "npc_dota_fort" )
	local hero = HeroList:GetHero( 0 )
	local ok = GetMapName() == "m1_dota" and towers >= 20 and ancients == 2 and hero ~= nil
	print( string.format( "[MCP_TEST12] map=%s towers=%d ancients=%d hero=%s -> %s",
		GetMapName(), towers, ancients, tostring( hero and hero:GetUnitName() ), ok and "PASS" or "FAIL" ) )
end, "MCP Lab: stage 12 part 1 (stock map copy loaded: towers, ancients, hero)", 0 )

-- Part 2: invisible obstacles spawned from Lua (point_simple_obstruction) + a polygon zone around the hero.
-- Leaving the polygon -> knockback back inside and a "Зона" line in the rift HUD.
local zone = nil

local function PointInPolygon( p, poly )
	local inside, j = false, #poly
	for i = 1, #poly do
		local a, b = poly[i], poly[j]
		if ( ( a.y > p.y ) ~= ( b.y > p.y ) ) and ( p.x < ( b.x - a.x ) * ( p.y - a.y ) / ( b.y - a.y ) + a.x ) then
			inside = not inside
		end
		j = i
	end
	return inside
end

local function SendZone( state )
	zone.state = state
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_zone", { state = state, pushes = zone.pushes } )
end

local function StartZone( hero )
	local c = hero:GetAbsOrigin()
	zone = { center = c, poly = {}, pushes = 0, obstacles = {} }
	for i = 0, 4 do  -- pentagon, radius 700
		local a = math.rad( 90 + i * 72 )
		table.insert( zone.poly, Vector( c.x + 700 * math.cos( a ), c.y + 700 * math.sin( a ), c.z ) )
	end
	for i = -2, 2 do  -- a wall of invisible obstacles 300 units east of the hero
		local pos = GetGroundPosition( c + Vector( 300, i * 64, 0 ), nil )
		local ent = SpawnEntityFromTableSynchronous( "point_simple_obstruction", { origin = pos, block_fow = false } )
		table.insert( zone.obstacles, { ent = ent, pos = pos } )
	end
	SendZone( "inside" )
	hero:SetContextThink( "MCPLab12Zone", function()
		if not zone or not hero:IsAlive() then return 0.1 end
		local p = hero:GetAbsOrigin()
		if PointInPolygon( p, zone.poly ) then
			if zone.state ~= "inside" and not hero:HasModifier( "modifier_knockback" ) then SendZone( "inside" ) end
		elseif not hero:HasModifier( "modifier_knockback" ) then
			local from = p + ( p - zone.center ):Normalized() * 100  -- knockback pushes away from this point = towards the center
			hero:AddNewModifier( hero, nil, "modifier_knockback", {
				center_x = from.x, center_y = from.y, center_z = from.z, duration = 0.5,
				knockback_duration = 0.5, knockback_distance = 350, knockback_height = 80, should_stun = 1,
			} )
			zone.pushes = zone.pushes + 1
			SendZone( "pushed" )
		end
		return 0.1
	end, 0.1 )
end

local function StopZone( hero )
	if not zone then return end
	hero:SetContextThink( "MCPLab12Zone", nil, 0 )
	for _, o in ipairs( zone.obstacles ) do if IsValidEntity( o.ent ) then UTIL_Remove( o.ent ) end end
	zone = nil
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_zone", { state = "off", pushes = 0 } )
end

local zone_ack, video_ack = nil, nil
-- Listeners registered while the file is required (before Activate) never fire: register on first use instead
local listening = false
local function Listen()
	if listening then return end
	listening = true
	CustomGameEventManager:RegisterListener( "mcp_lab_zone_ack", function( _, data ) zone_ack = data end )
	CustomGameEventManager:RegisterListener( "mcp_lab_video_ack", function( _, data ) video_ack = data end )
end

Convars:RegisterCommand( "mcp_lab_zone", function( _, arg )
	Listen()
	local hero = HeroList:GetHero( 0 )
	StopZone( hero )
	if arg ~= "0" then StartZone( hero ) end
end, "MCP Lab: polygon zone + invisible obstacles around the hero (0 = off)", 0 )

Convars:RegisterCommand( "mcp_lab_autotest12_zone", function()
	Listen()
	local hero = HeroList:GetHero( 0 )
	StopZone( hero ); StartZone( hero )
	zone_ack = nil
	local blocked = 0
	for _, o in ipairs( zone.obstacles ) do
		if GridNav:IsBlocked( o.pos ) or not GridNav:IsTraversable( o.pos ) then blocked = blocked + 1 end
	end
	local c = zone.center
	FindClearSpaceForUnit( hero, c + Vector( -900, 0, 0 ), true )  -- outside the pentagon, away from the obstacles
	local d0 = ( hero:GetAbsOrigin() - c ):Length2D()
	GameRules:GetGameModeEntity():SetContextThink( "MCPLab12ZoneCheck", function()
		local d1 = ( hero:GetAbsOrigin() - c ):Length2D()
		local hud = zone_ack and zone_ack.text or "?"
		local ok = blocked == #zone.obstacles and zone.pushes >= 1 and d1 < d0 - 200 and zone_ack ~= nil
		print( string.format( "[MCP_TEST12] zone obstacles_blocked=%d/%d pushes=%d dist %.0f -> %.0f hud='%s' -> %s",
			blocked, #zone.obstacles, zone.pushes, d0, d1, hud, ok and "PASS" or "FAIL" ) )
	end, 1.5 )
end, "MCP Lab: stage 12 part 2 (obstacles block the grid, leaving the zone knocks back, HUD line)", 0 )

-- Part 4: a neutral boss whose model grows smoothly from 0.5x to 1.5x (lerp every 0.05 s for 3 s).
local function GrowBoss( unit, from, to, seconds, samples )
	local t0 = GameRules:GetGameTime()
	unit:SetModelScale( from )
	unit:SetContextThink( "MCPLab12Grow", function()
		local k = math.min( 1, ( GameRules:GetGameTime() - t0 ) / seconds )
		unit:SetModelScale( from + ( to - from ) * k )
		if samples then table.insert( samples, unit:GetModelScale() ) end
		if k < 1 then return 0.05 end
	end, 0 )
end

local function SpawnBoss( hero )
	return CreateUnitByName( "npc_dota_neutral_granite_golem", hero:GetAbsOrigin() + Vector( 0, 400, 0 ), true, nil, nil, DOTA_TEAM_NEUTRALS )
end

Convars:RegisterCommand( "mcp_lab_growboss", function()
	GrowBoss( SpawnBoss( HeroList:GetHero( 0 ) ), 0.5, 1.5, 3 )
end, "MCP Lab: spawn a neutral golem boss growing 0.5x -> 1.5x", 0 )

Convars:RegisterCommand( "mcp_lab_autotest12_scale", function()
	local boss = SpawnBoss( HeroList:GetHero( 0 ) )
	local samples = {}
	GrowBoss( boss, 0.5, 1.5, 3, samples )
	GameRules:GetGameModeEntity():SetContextThink( "MCPLab12ScaleCheck", function()
		local monotonic, max_step = true, 0
		for i = 2, #samples do
			if samples[i] < samples[i - 1] then monotonic = false end
			max_step = math.max( max_step, samples[i] - samples[i - 1] )
		end
		local final = boss:GetModelScale()
		local ok = #samples >= 30 and monotonic and max_step <= 0.05 and math.abs( final - 1.5 ) < 0.01 and samples[1] < 0.6
		print( string.format( "[MCP_TEST12] scale samples=%d first=%.2f final=%.2f max_step=%.3f monotonic=%s -> %s",
			#samples, samples[1] or -1, final, max_step, tostring( monotonic ), ok and "PASS" or "FAIL" ) )
		UTIL_Remove( boss )
	end, 3.5 )
end, "MCP Lab: stage 12 part 4 (neutral boss model scale 0.5 -> 1.5 smooth)", 0 )

-- Part 5: own item with a stock icon (Frost Band), recipe from 2 stock parts, overflow goes to the backpack.
Convars:RegisterCommand( "mcp_lab_autotest12_item", function()
	local hero = HeroList:GetHero( 0 )
	for slot = 0, 8 do local it = hero:GetItemInSlot( slot ); if it then hero:RemoveItem( it ) end end
	hero:AddItemByName( "item_circlet" )
	hero:AddItemByName( "item_mantle" )
	GameRules:GetGameModeEntity():SetContextThink( "MCPLab12ItemCheck", function()
		local band = hero:FindItemInInventory( "item_mcp_frost_band" )
		local parts_left = hero:FindItemInInventory( "item_circlet" ) or hero:FindItemInInventory( "item_mantle" )
		local has_mod = hero:HasModifier( "modifier_item_mcp_frost_band" )
		for _ = 1, 5 do hero:AddItemByName( "item_branches" ) end  -- band + 5 branches = full main inventory
		local extra = hero:AddItemByName( "item_mcp_frost_band" )   -- 7th item -> backpack (slots 6..8)
		local extra_slot = extra and extra:GetItemSlot() or -1
		local texture = GetAbilityTextureNameForAbility( "item_mcp_frost_band" ) or "-"
		local ok = band ~= nil and parts_left == nil and has_mod and extra_slot >= 6 and extra_slot <= 8 and texture == "item_wraith_band"
		print( string.format( "[MCP_TEST12] item combined=%s parts_left=%s modifier=%s texture=%s backpack_slot=%d -> %s",
			tostring( band ~= nil ), tostring( parts_left ~= nil ), tostring( has_mod ), texture, extra_slot, ok and "PASS" or "FAIL" ) )
	end, 0.5 )
end, "MCP Lab: stage 12 part 5 (own item, stock icon, 2-part recipe, backpack)", 0 )

-- Part 6: .webm in a Panorama Movie panel. Stock videos are loose files in game/dota/panorama/videos,
-- ours are loose in game/dota_addons/mcp_lab/panorama/videos (small 0.2 MB, big 29 MB; no compile step).
local VIDEOS = {
	stock = "file://{resources}/videos/dota_logo_portrait.webm",
	small = "file://{resources}/videos/mcp_lab_small.webm",
	big = "file://{resources}/videos/mcp_lab_big.webm",
}

Convars:RegisterCommand( "mcp_lab_video", function( _, which )
	Listen()
	video_ack = nil
	CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_video", { src = VIDEOS[ which or "small" ] or "" } )
	GameRules:GetGameModeEntity():SetContextThink( "MCPLab12VideoCheck", function()
		print( string.format( "[MCP_TEST12] video %s ack=%s shown=%s", tostring( which ),
			tostring( video_ack and video_ack.src ), tostring( video_ack and video_ack.shown ) ) )
	end, 0.5 )
end, "MCP Lab: show a webm in the HUD (stock | small | big | 0 = hide)", 0 )

-- Part 7: stock hero voice lines from Lua; a Russian client mounts dota_russian, which replaces the same sound paths.
local VOICE = { "crystalmaiden_cm_laugh_01", "templar_assassin_temp_laugh_01", "witchdoctor_wdoc_laugh_01", "ursa_ursa_laugh_01" }

Convars:RegisterCommand( "mcp_lab_voice", function( _, which )
	local hero = HeroList:GetHero( 0 )
	local list = VOICE[ tonumber( which or "" ) or 0 ] and { VOICE[ tonumber( which ) ] } or VOICE
	for i, name in ipairs( list ) do
		hero:SetContextThink( "MCPLab12Voice" .. i, function()
			EmitSoundOnClient( name, hero:GetPlayerOwner() )
			print( "[MCP_TEST12] voice " .. name )
		end, ( i - 1 ) * 2.5 )
	end
end, "MCP Lab: play stock voice lines CM, TA, WD, Ursa (1..4 = only one of them)", 0 )
