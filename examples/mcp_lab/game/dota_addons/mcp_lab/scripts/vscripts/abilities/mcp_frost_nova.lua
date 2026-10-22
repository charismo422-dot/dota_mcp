LinkLuaModifier( "modifier_mcp_frost_nova_slow", "abilities/mcp_frost_nova", LUA_MODIFIER_MOTION_NONE )

mcp_frost_nova = class({})

function mcp_frost_nova:GetAOERadius()
	return self:GetSpecialValueFor( "radius" )
end

function mcp_frost_nova:OnSpellStart()
	if not IsServer() then return end

	local caster = self:GetCaster()
	local point = self:GetCursorPosition()
	local radius = self:GetSpecialValueFor( "radius" )
	local damage = self:GetSpecialValueFor( "nova_damage" )
	local duration = self:GetSpecialValueFor( "duration" )

	-- CP0 = position, CP1 = (radius, duration, radius) as used by maiden_crystal_nova (CP1 confirmed via inspect_particle)
	local pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_crystalmaiden/maiden_crystal_nova.vpcf", PATTACH_WORLDORIGIN, nil )
	ParticleManager:SetParticleControl( pfx, 0, point )
	ParticleManager:SetParticleControl( pfx, 1, Vector( radius, duration, radius ) )
	ParticleManager:ReleaseParticleIndex( pfx )

	EmitSoundOnLocationWithCaster( point, "Hero_Crystal.CrystalNova", caster )
	AddFOWViewer( caster:GetTeamNumber(), point, radius, self:GetSpecialValueFor( "vision_duration" ), false )

	local enemies = FindUnitsInRadius(
		caster:GetTeamNumber(),
		point,
		nil,
		radius,
		DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC,
		DOTA_UNIT_TARGET_FLAG_NONE,
		0,
		false
	)

	for _, enemy in pairs( enemies ) do
		ApplyDamage({
			victim = enemy,
			attacker = caster,
			damage = damage,
			damage_type = DAMAGE_TYPE_MAGICAL,
			ability = self,
		})
		enemy:AddNewModifier( caster, self, "modifier_mcp_frost_nova_slow", { duration = duration } )
	end
	print( string.format( "[MCP_LAB] mcp_frost_nova cast (hot-reloaded v2): radius=%d damage=%d targets_hit=%d", radius, damage, #enemies ) )
end

--------------------------------------------------------------------------------

modifier_mcp_frost_nova_slow = class({})

function modifier_mcp_frost_nova_slow:IsDebuff()
	return true
end

function modifier_mcp_frost_nova_slow:OnCreated()
	self.movespeed_slow = self:GetAbility():GetSpecialValueFor( "movespeed_slow" )
	self.attackspeed_slow = self:GetAbility():GetSpecialValueFor( "attackspeed_slow" )
end

function modifier_mcp_frost_nova_slow:DeclareFunctions()
	return {
		MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE,
		MODIFIER_PROPERTY_ATTACKSPEED_BONUS_CONSTANT,
	}
end

function modifier_mcp_frost_nova_slow:GetModifierMoveSpeedBonus_Percentage()
	return self.movespeed_slow
end

function modifier_mcp_frost_nova_slow:GetModifierAttackSpeedBonus_Constant()
	return self.attackspeed_slow
end

function modifier_mcp_frost_nova_slow:GetEffectName()
	return "particles/generic_gameplay/generic_slowed_cold.vpcf"
end

function modifier_mcp_frost_nova_slow:GetEffectAttachType()
	return PATTACH_ABSORIGIN_FOLLOW
end
