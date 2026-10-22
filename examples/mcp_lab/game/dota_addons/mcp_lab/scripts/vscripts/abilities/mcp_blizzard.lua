LinkLuaModifier( "modifier_mcp_blizzard_thinker", "abilities/mcp_blizzard", LUA_MODIFIER_MOTION_NONE )

mcp_blizzard = class({})

function mcp_blizzard:OnSpellStart()
	if not IsServer() then return end
	local caster = self:GetCaster()
	CreateModifierThinker( caster, self, "modifier_mcp_blizzard_thinker", { duration = self:GetSpecialValueFor( "duration" ) },
		caster:GetAbsOrigin(), caster:GetTeamNumber(), false )
end

--------------------------------------------------------------------------------

modifier_mcp_blizzard_thinker = class({})

function modifier_mcp_blizzard_thinker:OnCreated()
	if not IsServer() then return end
	local ability = self:GetAbility()
	self.radius = ability:GetSpecialValueFor( "radius" )
	self.damage = ability:GetSpecialValueFor( "damage_per_tick" )
	self.ticks = 0
	self:StartIntervalThink( ability:GetSpecialValueFor( "interval" ) )
	-- Stock wind sound lasts as long as CM's 10 s ultimate: emit it on the thinker and stop it when our 3 s end
	EmitSoundOn( "hero_Crystal.freezingField.wind", self:GetParent() )
end

function modifier_mcp_blizzard_thinker:OnIntervalThink()
	local thinker = self:GetParent()
	local caster = self:GetCaster()
	local center = thinker:GetAbsOrigin()

	-- One explosion at a random point inside the radius per tick
	local point = center + RandomVector( RandomFloat( 0, self.radius ) )
	local pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_crystalmaiden/maiden_freezing_field_explosion.vpcf", PATTACH_WORLDORIGIN, nil )
	ParticleManager:SetParticleControl( pfx, 0, point )
	ParticleManager:SetParticleControl( pfx, 3, point )
	ParticleManager:ReleaseParticleIndex( pfx )
	EmitSoundOnLocationWithCaster( point, "hero_Crystal.freezingField.explosion", caster )

	local enemies = FindUnitsInRadius( caster:GetTeamNumber(), center, nil, self.radius, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_NONE, 0, false )
	for _, enemy in pairs( enemies ) do
		ApplyDamage({ victim = enemy, attacker = caster, damage = self.damage, damage_type = DAMAGE_TYPE_MAGICAL, ability = self:GetAbility() })
	end
	self.ticks = self.ticks + 1
end

function modifier_mcp_blizzard_thinker:OnDestroy()
	if not IsServer() then return end
	print( string.format( "[MCP_LAB] mcp_blizzard finished: ticks=%d", self.ticks ) )
	StopSoundOn( "hero_Crystal.freezingField.wind", self:GetParent() )
	UTIL_Remove( self:GetParent() )
end
