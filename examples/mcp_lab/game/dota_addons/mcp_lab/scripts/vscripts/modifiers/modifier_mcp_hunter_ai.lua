-- Stage 9: Lua AI for stock enemy heroes (no player owner). Everything is done with orders, like a player would:
-- chase + attack the closest enemy hero, cast 1-2 stock abilities, retreat below 30% HP, come back at 80%.
modifier_mcp_hunter_ai = class({})

-- Stock ability names come from get_base_dota_definition; ranges are the KV cast ranges
local SPELLS = {
	npc_dota_hero_sven = { { name = "sven_storm_bolt", kind = "target", range = 600 }, { name = "sven_warcry", kind = "none", range = 500 } },
	npc_dota_hero_lina = { { name = "lina_light_strike_array", kind = "point", range = 700 }, { name = "lina_dragon_slave", kind = "point", range = 1000 } },
}

local RETREAT_BELOW, RETURN_ABOVE = 30, 80

function modifier_mcp_hunter_ai:IsHidden() return true end
function modifier_mcp_hunter_ai:IsPurgable() return false end

function modifier_mcp_hunter_ai:OnCreated( kv )
	if not IsServer() then return end
	local unit = self:GetParent()
	self.home = Vector( kv.home_x or unit:GetAbsOrigin().x, kv.home_y or unit:GetAbsOrigin().y, unit:GetAbsOrigin().z )
	self.spells = SPELLS[ unit:GetUnitName() ] or {}
	self.state, self.casts, self.retreats, self.returns = "hunt", {}, 0, 0
	self:StartIntervalThink( 0.25 )
end

function modifier_mcp_hunter_ai:DeclareFunctions()
	return { MODIFIER_PROPERTY_HEALTH_REGEN_PERCENTAGE }
end

-- Retreating hunters heal quickly so that "retreat and come back" is visible within a few seconds
function modifier_mcp_hunter_ai:GetModifierHealthRegenPercentage()
	return self.state == "retreat" and 8 or 0
end

function modifier_mcp_hunter_ai:OnIntervalThink()
	local unit = self:GetParent()
	if not unit:IsAlive() or unit:IsChanneling() then return end
	for _, s in ipairs( self.spells ) do
		local ab = unit:FindAbilityByName( s.name )
		if ab and ab:IsInAbilityPhase() then return end
	end

	local hp = unit:GetHealthPercent()
	if self.state == "hunt" and hp < RETREAT_BELOW then
		self.state = "retreat"
		self.retreats = self.retreats + 1
		unit:MoveToPosition( self.home )
		return
	end
	if self.state == "retreat" then
		if hp < RETURN_ABOVE then
			if not unit:IsMoving() and ( unit:GetAbsOrigin() - self.home ):Length2D() > 100 then unit:MoveToPosition( self.home ) end
			return
		end
		self.state = "hunt"
		self.returns = self.returns + 1
	end

	local heroes = FindUnitsInRadius( unit:GetTeamNumber(), unit:GetAbsOrigin(), nil, 2500, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO, DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, false )
	local target = heroes[1]
	if not target then
		if not unit:IsMoving() and ( unit:GetAbsOrigin() - self.home ):Length2D() > 200 then unit:MoveToPositionAggressive( self.home ) end
		return
	end

	local dist = ( target:GetAbsOrigin() - unit:GetAbsOrigin() ):Length2D()
	for _, s in ipairs( self.spells ) do
		local ab = unit:FindAbilityByName( s.name )
		if ab and ab:GetLevel() > 0 and ab:IsFullyCastable() and dist <= s.range then
			if s.kind == "target" then
				unit:CastAbilityOnTarget( target, ab, -1 )
			elseif s.kind == "point" then
				unit:CastAbilityOnPosition( target:GetAbsOrigin(), ab, -1 )
			else
				unit:CastAbilityNoTarget( ab, -1 )
			end
			self.casts[ s.name ] = ( self.casts[ s.name ] or 0 ) + 1
			return
		end
	end
	if unit:GetAggroTarget() ~= target then
		unit:MoveToTargetToAttack( target )
	end
end
