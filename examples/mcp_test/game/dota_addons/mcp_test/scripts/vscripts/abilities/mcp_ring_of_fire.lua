LinkLuaModifier( "modifier_mcp_ring_of_fire_delay", "abilities/mcp_ring_of_fire", LUA_MODIFIER_MOTION_NONE )

mcp_ring_of_fire = class({})

function mcp_ring_of_fire:GetAOERadius()
	return self:GetSpecialValueFor( "radius" )
end

function mcp_ring_of_fire:OnSpellStart()
	if not IsServer() then return end

	local caster = self:GetCaster()
	local delay = self:GetSpecialValueFor( "delay" )

	EmitSoundOn( "Ability.PreLightStrikeArray", caster )
	caster:AddNewModifier( caster, self, "modifier_mcp_ring_of_fire_delay", { duration = delay } )
	print( string.format( "[MCP_TEST] mcp_ring_of_fire OnSpellStart: delay=%.2fs", delay ) )
end

--------------------------------------------------------------------------------

modifier_mcp_ring_of_fire_delay = class({})

function modifier_mcp_ring_of_fire_delay:IsHidden()
	return false
end

function modifier_mcp_ring_of_fire_delay:IsPurgable()
	return false
end

function modifier_mcp_ring_of_fire_delay:OnCreated( kv )
	if not IsServer() then return end

	local parent = self:GetParent()
	local ability = self:GetAbility()
	local radius = 500
	local delay = 1.0
	if ability then
		radius = ability:GetSpecialValueFor( "radius" )
		delay = ability:GetSpecialValueFor( "delay" )
	end

	-- Ground preparation ring following hero position (PATTACH_ABSORIGIN_FOLLOW):
	-- CP0 follows parent origin; CP1.x = radius, CP1.z = speed multiplier (confirmed in C_INIT_RingWave)
	local pfx = ParticleManager:CreateParticle(
		"particles/units/heroes/hero_lina/lina_spell_light_strike_array_ring_collapse.vpcf",
		PATTACH_ABSORIGIN_FOLLOW,
		parent
	)
	ParticleManager:SetParticleControl( pfx, 1, Vector( radius, 0, 1.0 / math.max( delay, 0.1 ) ) )
	self.pre_pfx = pfx
end

function modifier_mcp_ring_of_fire_delay:OnDestroy()
	if not IsServer() then return end

	if self.pre_pfx then
		ParticleManager:DestroyParticle( self.pre_pfx, false )
		ParticleManager:ReleaseParticleIndex( self.pre_pfx )
		self.pre_pfx = nil
	end

	local parent = self:GetParent()
	local ability = self:GetAbility()
	if not parent or not parent:IsAlive() or not ability then
		return
	end

	local radius = ability:GetSpecialValueFor( "radius" )
	local damage = ability:GetSpecialValueFor( "damage" )
	local origin = parent:GetAbsOrigin()

	EmitSoundOn( "Hero_Huskar.Inner_Fire.Cast", parent )

	local fire_pfx = ParticleManager:CreateParticle(
		"particles/units/heroes/hero_huskar/huskar_inner_fire.vpcf",
		PATTACH_ABSORIGIN_FOLLOW,
		parent
	)
	ParticleManager:SetParticleControl( fire_pfx, 0, origin )
	ParticleManager:SetParticleControl( fire_pfx, 1, Vector( radius, 0, 0 ) )
	ParticleManager:ReleaseParticleIndex( fire_pfx )

	local enemies = FindUnitsInRadius(
		parent:GetTeamNumber(),
		origin,
		nil,
		radius,
		DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC,
		DOTA_UNIT_TARGET_FLAG_NONE,
		0,
		false
	)

	local hit_count = 0
	for _, enemy in pairs( enemies ) do
		if enemy and enemy:IsAlive() then
			ApplyDamage({
				victim = enemy,
				attacker = parent,
				damage = damage,
				damage_type = DAMAGE_TYPE_MAGICAL,
				ability = ability,
			})
			hit_count = hit_count + 1
		end
	end
	print( string.format( "[MCP_TEST] mcp_ring_of_fire Erupted! radius=%d, damage=%d, targets_hit=%d", radius, damage, hit_count ) )
end
