LinkLuaModifier( "modifier_mcp_giant_slam_stun", "abilities/mcp_giant_slam", LUA_MODIFIER_MOTION_NONE )

mcp_giant_slam = class({})

-- Telegraph: a collapsing ring shows the danger zone for the whole cast point, so players can step out
function mcp_giant_slam:OnAbilityPhaseStart()
	if not IsServer() then return true end
	local caster = self:GetCaster()
	local radius = self:GetSpecialValueFor( "radius" )
	-- CP1 = (radius, 0, collapse speed); same CP layout as used in examples/mcp_test (C_INIT_RingWave)
	self.warning_pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_lina/lina_spell_light_strike_array_ring_collapse.vpcf", PATTACH_ABSORIGIN, caster )
	ParticleManager:SetParticleControl( self.warning_pfx, 1, Vector( radius, 0, 1.0 / self:GetCastPoint() ) )
	return true
end

function mcp_giant_slam:ClearWarning()
	if self.warning_pfx then
		ParticleManager:DestroyParticle( self.warning_pfx, true )
		ParticleManager:ReleaseParticleIndex( self.warning_pfx )
		self.warning_pfx = nil
	end
end

function mcp_giant_slam:OnAbilityPhaseInterrupted()
	self:ClearWarning()
end

function mcp_giant_slam:OnSpellStart()
	if not IsServer() then return end
	self:ClearWarning()

	local caster = self:GetCaster()
	local origin = caster:GetAbsOrigin()
	local radius = self:GetSpecialValueFor( "radius" )

	local pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_centaur/centaur_warstomp.vpcf", PATTACH_WORLDORIGIN, nil )
	ParticleManager:SetParticleControl( pfx, 0, origin )
	ParticleManager:SetParticleControl( pfx, 1, Vector( radius, radius, radius ) )
	ParticleManager:ReleaseParticleIndex( pfx )
	EmitSoundOnLocationWithCaster( origin, "Hero_Centaur.HoofStomp", caster )

	local enemies = FindUnitsInRadius( caster:GetTeamNumber(), origin, nil, radius, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_NONE, 0, false )
	for _, enemy in pairs( enemies ) do
		ApplyDamage({ victim = enemy, attacker = caster, damage = self:GetSpecialValueFor( "damage" ), damage_type = DAMAGE_TYPE_MAGICAL, ability = self })
		enemy:AddNewModifier( caster, self, "modifier_mcp_giant_slam_stun", { duration = self:GetSpecialValueFor( "stun_duration" ) } )
	end
	GameRules.mcp_lab_slam_hits = ( GameRules.mcp_lab_slam_hits or 0 ) + #enemies
	print( "[MCP_LAB] mcp_giant_slam hit " .. #enemies )
end

--------------------------------------------------------------------------------

modifier_mcp_giant_slam_stun = class({})

function modifier_mcp_giant_slam_stun:IsDebuff() return true end
function modifier_mcp_giant_slam_stun:IsStunDebuff() return true end
function modifier_mcp_giant_slam_stun:CheckState() return { [MODIFIER_STATE_STUNNED] = true } end
function modifier_mcp_giant_slam_stun:GetEffectName() return "particles/generic_gameplay/generic_stunned.vpcf" end
function modifier_mcp_giant_slam_stun:GetEffectAttachType() return PATTACH_OVERHEAD_FOLLOW end
