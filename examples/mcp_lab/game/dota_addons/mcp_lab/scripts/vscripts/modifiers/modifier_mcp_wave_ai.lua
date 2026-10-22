-- Simple wave AI: chase the nearest enemy hero; units with mcp_giant_slam use it when a hero is in range
modifier_mcp_wave_ai = class({})

function modifier_mcp_wave_ai:IsHidden() return true end
function modifier_mcp_wave_ai:IsPurgable() return false end

function modifier_mcp_wave_ai:OnCreated()
	if not IsServer() then return end
	self.slam = self:GetParent():FindAbilityByName( "mcp_giant_slam" )
	self:StartIntervalThink( 0.5 )
end

function modifier_mcp_wave_ai:OnIntervalThink()
	local unit = self:GetParent()
	if not unit:IsAlive() or unit:IsChanneling() or ( self.slam and self.slam:IsInAbilityPhase() ) then return end

	local heroes = FindUnitsInRadius( unit:GetTeamNumber(), unit:GetAbsOrigin(), nil, 3000, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO, DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, false )
	local target = heroes[1]
	if not target then return end

	if self.slam and self.slam:IsFullyCastable() and ( target:GetAbsOrigin() - unit:GetAbsOrigin() ):Length2D() <= self.slam:GetSpecialValueFor( "radius" ) - 50 then
		unit:CastAbilityNoTarget( self.slam, -1 )
		return
	end
	if unit:GetAggroTarget() ~= target then
		unit:MoveToTargetToAttack( target )
	end
end
