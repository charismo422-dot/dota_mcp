-- MCP Lab stage 13: autotest of an ability made by the scaffold_game_element tool (mcp_rift_quake)

Convars:RegisterCommand( "mcp_lab_autotest13", function()
	local hero = GameRules.AddonTemplate and GameRules.AddonTemplate.hero
	if not hero then print( "[MCP_LAB] AUTOTEST stage13 FAIL: no hero" ) return end

	local name = "mcp_rift_quake"
	local ability = hero:FindAbilityByName( name ) or hero:AddAbility( name )
	if not ability then print( "[MCP_LAB] AUTOTEST stage13 FAIL: AddAbility returned nil" ) return end
	ability:SetLevel( 1 )
	ability:EndCooldown()
	hero:SetMana( hero:GetMaxMana() )
	hero:SetHealth( math.max( 1, hero:GetMaxHealth() - 300 ) )
	local hero_hp = hero:GetHealth()

	local center = hero:GetAbsOrigin() + hero:GetForwardVector() * 400
	local creep = CreateUnitByName( "npc_dota_creep_badguys_melee", center, true, nil, nil, DOTA_TEAM_BADGUYS )
	local far = CreateUnitByName( "npc_dota_creep_badguys_melee", center + Vector( 900, 0, 0 ), true, nil, nil, DOTA_TEAM_BADGUYS )
	local creep_hp, far_hp, base_ms = creep:GetHealth(), far:GetHealth(), creep:GetIdealSpeed()

	hero:SetContextThink( "mcp_lab_autotest13_cast", function()
		hero:CastAbilityOnPosition( center, ability, hero:GetPlayerOwnerID() )
		return nil
	end, 0.3 )
	hero:SetContextThink( "mcp_lab_autotest13_check", function()
		local checks = {
			{ "cast", ability:GetCooldownTimeRemaining() > 0 },
			{ "damage", creep:IsAlive() == false or creep:GetHealth() < creep_hp },
			{ "stun", creep:IsAlive() == false or creep:HasModifier( "modifier_stunned" ) },
			{ "slow_modifier", creep:IsAlive() == false or creep:HasModifier( "modifier_mcp_rift_quake_debuff" ) },
			{ "slowed", creep:IsAlive() == false or creep:GetIdealSpeed() < base_ms },
			{ "heal", hero:GetHealth() > hero_hp },
			{ "radius", far:GetHealth() == far_hp },
		}
		local all_ok, parts = true, {}
		for _, c in ipairs( checks ) do
			all_ok = all_ok and c[2]
			table.insert( parts, c[1] .. "=" .. ( c[2] and "ok" or "FAIL" ) )
		end
		print( string.format( "[MCP_LAB] AUTOTEST stage13 %s: %s creep_hp %d->%d ms %d->%d", all_ok and "PASS" or "FAIL",
			table.concat( parts, " " ), creep_hp, creep:GetHealth(), base_ms, creep:GetIdealSpeed() ) )
		UTIL_Remove( creep )
		UTIL_Remove( far )
		return nil
	end, 1.2 )
end, "MCP Lab: stage 13 autotest (ability made by scaffold_game_element)", 0 )
