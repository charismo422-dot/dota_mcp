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
