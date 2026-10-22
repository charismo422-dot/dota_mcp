LinkLuaModifier( "modifier_mcp_ice_bolt_stun", "abilities/mcp_ice_bolt", LUA_MODIFIER_MOTION_NONE )

mcp_ice_bolt = class({})

function mcp_ice_bolt:OnSpellStart()
	if not IsServer() then return end
	local caster = self:GetCaster()

	-- Projectile starts at attach_attack1 (staff), confirmed on crystal_maiden.vmdl via inspect_model
	ProjectileManager:CreateTrackingProjectile({
		Target = self:GetCursorTarget(),
		Source = caster,
		Ability = self,
		EffectName = "particles/units/heroes/hero_crystalmaiden/maiden_base_attack.vpcf",
		iMoveSpeed = self:GetSpecialValueFor( "projectile_speed" ),
		iSourceAttachment = DOTA_PROJECTILE_ATTACHMENT_ATTACK_1,
		bDodgeable = false,
	})
	EmitSoundOn( "hero_Crystal.attack", caster )
end

function mcp_ice_bolt:OnProjectileHit( target, location )
	if not target or target:IsInvulnerable() then return true end

	ApplyDamage({
		victim = target,
		attacker = self:GetCaster(),
		damage = self:GetSpecialValueFor( "damage" ),
		damage_type = DAMAGE_TYPE_MAGICAL,
		ability = self,
	})
	target:AddNewModifier( self:GetCaster(), self, "modifier_mcp_ice_bolt_stun", { duration = self:GetSpecialValueFor( "stun_duration" ) } )
	EmitSoundOn( "hero_Crystal.frostbite", target )
	print( "[MCP_LAB] mcp_ice_bolt hit " .. target:GetUnitName() )
	return true
end

--------------------------------------------------------------------------------

modifier_mcp_ice_bolt_stun = class({})

function modifier_mcp_ice_bolt_stun:IsDebuff()
	return true
end

function modifier_mcp_ice_bolt_stun:IsStunDebuff()
	return true
end

function modifier_mcp_ice_bolt_stun:CheckState()
	return { [MODIFIER_STATE_STUNNED] = true }
end

function modifier_mcp_ice_bolt_stun:GetEffectName()
	return "particles/units/heroes/hero_crystalmaiden/maiden_frostbite.vpcf"
end

function modifier_mcp_ice_bolt_stun:GetEffectAttachType()
	return PATTACH_ABSORIGIN_FOLLOW
end
