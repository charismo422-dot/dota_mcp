-- Scaffolded by dota2-workshop-mcp (scaffold_game_element); edit freely
require( "mcp_scaffold_links" )  -- ability scripts also load on the client VM, which needs the links
LinkLuaModifier( "modifier_mcp_rift_quake_debuff", "abilities/mcp_rift_quake", LUA_MODIFIER_MOTION_NONE )

mcp_rift_quake = class({})

function mcp_rift_quake:GetAOERadius()
	return self:GetSpecialValueFor( "radius" )
end

function mcp_rift_quake:OnSpellStart()
	if not IsServer() then return end

	local caster = self:GetCaster()
	local center = self:GetCursorPosition()
	local targets = FindUnitsInRadius( caster:GetTeamNumber(), center, nil,
		self:GetSpecialValueFor( "radius" ), DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_NONE, 0, false )

	-- CP0 = position; CP1 = radius (the particle reads CP1)
	local pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_leshrac/leshrac_split_earth.vpcf", PATTACH_WORLDORIGIN, nil )
	ParticleManager:SetParticleControl( pfx, 0, center )
	local radius = self:GetSpecialValueFor( "radius" )
	ParticleManager:SetParticleControl( pfx, 1, Vector( radius, radius, radius ) )
	ParticleManager:ReleaseParticleIndex( pfx )
	EmitSoundOnLocationWithCaster( center, "Hero_Leshrac.Split_Earth", caster )

	for _, unit in pairs( targets ) do
		ApplyDamage({ victim = unit, attacker = caster, ability = self,
			damage = self:GetSpecialValueFor( "damage" ), damage_type = self:GetAbilityDamageType() })
		unit:AddNewModifier( caster, self, "modifier_stunned", { duration = self:GetSpecialValueFor( "stun_duration" ) } )
		unit:AddNewModifier( caster, self, "modifier_mcp_rift_quake_debuff", { duration = self:GetSpecialValueFor( "duration" ) } )
	end

	caster:Heal( self:GetSpecialValueFor( "heal" ), self )
	SendOverheadEventMessage( nil, OVERHEAD_ALERT_HEAL, caster, self:GetSpecialValueFor( "heal" ), nil )
end

--------------------------------------------------------------------------------

modifier_mcp_rift_quake_debuff = class({})

function modifier_mcp_rift_quake_debuff:IsHidden() return false end
function modifier_mcp_rift_quake_debuff:IsDebuff() return true end
function modifier_mcp_rift_quake_debuff:IsPurgable() return true end

function modifier_mcp_rift_quake_debuff:OnCreated( kv )
	local ability = self:GetAbility()
	-- values come from the ability (AbilityValues) when there is one, else from AddNewModifier params, else defaults
	self.slow = ( ability and ability:GetSpecialValueFor( "slow" ) ) or ( kv and tonumber( kv.slow ) ) or 30
end

function modifier_mcp_rift_quake_debuff:OnRefresh( kv )
	self:OnCreated( kv )
end

function modifier_mcp_rift_quake_debuff:DeclareFunctions()
	return { MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE }
end

function modifier_mcp_rift_quake_debuff:GetModifierMoveSpeedBonus_Percentage()
	return -self.slow
end
