LinkLuaModifier( "modifier_item_mcp_void_shard", "items/item_mcp_void_shard", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_item_mcp_void_shard_pull", "items/item_mcp_void_shard", LUA_MODIFIER_MOTION_HORIZONTAL )
LinkLuaModifier( "modifier_item_mcp_void_shard_rift", "items/item_mcp_void_shard", LUA_MODIFIER_MOTION_NONE )

item_mcp_void_shard = class({})

function item_mcp_void_shard:GetIntrinsicModifierName()
	return "modifier_item_mcp_void_shard"
end

function item_mcp_void_shard:GetAOERadius()
	return self:GetSpecialValueFor( "radius" )
end

-- Active: a rift (thinker entity) opens at the target point; after a short delay enemies inside are dragged into its center
function item_mcp_void_shard:OnSpellStart()
	if not IsServer() then return end
	local caster = self:GetCaster()
	CreateModifierThinker( caster, self, "modifier_item_mcp_void_shard_rift",
		{ duration = self:GetSpecialValueFor( "delay" ) + self:GetSpecialValueFor( "pull_duration" ) + 0.3 },
		self:GetCursorPosition(), caster:GetTeamNumber(), false )
end

--------------------------------------------------------------------------------
-- Rift thinker: owns the particle and the looping Black Hole sound, so both end together with it.
-- (A looping sound emitted with EmitSoundOnLocationWithCaster cannot be stopped and plays forever.)

modifier_item_mcp_void_shard_rift = class({})

function modifier_item_mcp_void_shard_rift:OnCreated()
	if not IsServer() then return end
	local ability = self:GetAbility()
	local center = self:GetParent():GetAbsOrigin()
	self.radius = ability:GetSpecialValueFor( "radius" )

	-- CP0 = position, CP1 = radius (enigma_blackhole uses CP1/CP2/CP62 per inspect_particle)
	self.pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_enigma/enigma_blackhole.vpcf", PATTACH_WORLDORIGIN, nil )
	ParticleManager:SetParticleControl( self.pfx, 0, center )
	ParticleManager:SetParticleControl( self.pfx, 1, Vector( self.radius, self.radius, self.radius ) )
	EmitSoundOn( "Hero_Enigma.Black_Hole", self:GetParent() )

	self:StartIntervalThink( ability:GetSpecialValueFor( "delay" ) )
end

function modifier_item_mcp_void_shard_rift:OnIntervalThink()
	self:StartIntervalThink( -1 )  -- pull only once
	local caster = self:GetCaster()
	local ability = self:GetAbility()
	local center = self:GetParent():GetAbsOrigin()
	local enemies = FindUnitsInRadius( caster:GetTeamNumber(), center, nil, self.radius, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC, DOTA_UNIT_TARGET_FLAG_NONE, 0, false )
	for _, enemy in pairs( enemies ) do
		enemy:AddNewModifier( caster, ability, "modifier_item_mcp_void_shard_pull",
			{ duration = ability:GetSpecialValueFor( "pull_duration" ), x = center.x, y = center.y } )
	end
	print( "[MCP_LAB] void shard pulled " .. #enemies )
end

function modifier_item_mcp_void_shard_rift:OnDestroy()
	if not IsServer() then return end
	local thinker = self:GetParent()
	ParticleManager:DestroyParticle( self.pfx, false )
	ParticleManager:ReleaseParticleIndex( self.pfx )
	StopSoundOn( "Hero_Enigma.Black_Hole", thinker )
	EmitSoundOnLocationWithCaster( thinker:GetAbsOrigin(), "Hero_Enigma.Black_Hole.Stop", self:GetCaster() )
	UTIL_Remove( thinker )
end

--------------------------------------------------------------------------------
-- Passive stats

modifier_item_mcp_void_shard = class({})

function modifier_item_mcp_void_shard:IsHidden() return true end
function modifier_item_mcp_void_shard:IsPurgable() return false end
function modifier_item_mcp_void_shard:GetAttributes() return MODIFIER_ATTRIBUTE_MULTIPLE end

function modifier_item_mcp_void_shard:DeclareFunctions()
	return { MODIFIER_PROPERTY_STATS_INTELLECT_BONUS, MODIFIER_PROPERTY_PHYSICAL_ARMOR_BONUS }
end

function modifier_item_mcp_void_shard:GetModifierBonusStats_Intellect()
	return self:GetAbility():GetSpecialValueFor( "bonus_intellect" )
end

function modifier_item_mcp_void_shard:GetModifierPhysicalArmorBonus()
	return self:GetAbility():GetSpecialValueFor( "bonus_armor" )
end

--------------------------------------------------------------------------------
-- Pull: horizontal motion controller dragging the unit into the rift center, then damage + silence

modifier_item_mcp_void_shard_pull = class({})

function modifier_item_mcp_void_shard_pull:IsDebuff() return true end
function modifier_item_mcp_void_shard_pull:IsStunDebuff() return true end

function modifier_item_mcp_void_shard_pull:OnCreated( kv )
	if not IsServer() then return end
	self.center = Vector( kv.x, kv.y, 0 )
	local parent = self:GetParent()
	local delta = self.center - parent:GetAbsOrigin()
	delta.z = 0
	self.speed = delta:Length2D() / math.max( self:GetDuration(), 0.05 )
	self.direction = delta:Normalized()
	if not self:ApplyHorizontalMotionController() then
		self:Destroy()
	end
end

function modifier_item_mcp_void_shard_pull:UpdateHorizontalMotion( me, dt )
	local pos = me:GetAbsOrigin()
	local remaining = ( self.center - pos ):Length2D()
	local step = math.min( self.speed * dt, remaining )
	me:SetAbsOrigin( pos + self.direction * step )
end

function modifier_item_mcp_void_shard_pull:OnHorizontalMotionInterrupted()
	self:Destroy()
end

function modifier_item_mcp_void_shard_pull:CheckState()
	return { [MODIFIER_STATE_STUNNED] = true }
end

function modifier_item_mcp_void_shard_pull:OnDestroy()
	if not IsServer() then return end
	local parent = self:GetParent()
	parent:RemoveHorizontalMotionController( self )
	FindClearSpaceForUnit( parent, parent:GetAbsOrigin(), true )
	local ability = self:GetAbility()
	if ability and parent:IsAlive() then
		ApplyDamage({ victim = parent, attacker = self:GetCaster(), damage = ability:GetSpecialValueFor( "damage" ), damage_type = DAMAGE_TYPE_MAGICAL, ability = ability })
		parent:AddNewModifier( self:GetCaster(), ability, "modifier_silence", { duration = ability:GetSpecialValueFor( "silence_duration" ) } )
	end
end
