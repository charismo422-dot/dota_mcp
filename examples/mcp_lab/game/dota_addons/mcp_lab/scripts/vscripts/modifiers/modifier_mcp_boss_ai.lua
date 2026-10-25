-- Stage 9: boss on a stock hero. Phase 1 -> (HP <= 60%) phase 2 -> (HP <= 30%) phase 3.
-- Every phase change is telegraphed for 1 s (boss stops, warning ring), then the phase action happens.
-- HP never drops below 1 until phase 3 is finished: the boss runs to a point and only then becomes killable.
modifier_mcp_boss_ai = class({})

local TELEGRAPH = 1.0

function modifier_mcp_boss_ai:IsHidden() return true end
function modifier_mcp_boss_ai:IsPurgable() return false end

function modifier_mcp_boss_ai:OnCreated( kv )
	self.mortal = false
	if not IsServer() then return end
	local unit = self:GetParent()
	self.run_point = Vector( kv.run_x or 0, kv.run_y or 0, unit:GetAbsOrigin().z )
	self.phase, self.state, self.log = 1, "fight", {}
	self.call = unit:FindAbilityByName( "axe_berserkers_call" )
	self.hunger = unit:FindAbilityByName( "axe_battle_hunger" )
	self:StartIntervalThink( 0.1 )
end

function modifier_mcp_boss_ai:DeclareFunctions()
	return { MODIFIER_PROPERTY_MIN_HEALTH, MODIFIER_PROPERTY_MODEL_SCALE, MODIFIER_PROPERTY_ATTACKSPEED_BONUS_CONSTANT, MODIFIER_PROPERTY_MOVESPEED_BONUS_CONSTANT }
end

function modifier_mcp_boss_ai:GetMinHealth() return self.mortal and 0 or 1 end
function modifier_mcp_boss_ai:GetModifierModelScale() return 30 end
function modifier_mcp_boss_ai:GetModifierAttackSpeedBonus_Constant() return ( self.phase or 1 ) >= 2 and 60 or 0 end
function modifier_mcp_boss_ai:GetModifierMoveSpeedBonus_Constant() return self.state == "run" and 150 or 0 end

function modifier_mcp_boss_ai:Note( what )
	table.insert( self.log, { what = what, time = GameRules:GetGameTime() } )
end

function modifier_mcp_boss_ai:StartTelegraph( next_phase )
	local unit = self:GetParent()
	self.state, self.next_phase = "telegraph", next_phase
	self.telegraph_end = GameRules:GetGameTime() + TELEGRAPH
	unit:Stop()
	unit:AddNewModifier( unit, nil, "modifier_mcp_boss_telegraph", { duration = TELEGRAPH } )
	self:Note( "telegraph" .. next_phase )
end

function modifier_mcp_boss_ai:OnIntervalThink()
	local unit = self:GetParent()
	if not unit:IsAlive() then return end
	local hp = unit:GetHealthPercent()

	if self.state == "telegraph" then
		if GameRules:GetGameTime() < self.telegraph_end then return end
		self.phase = self.next_phase
		self:Note( "phase" .. self.phase )
		if self.phase == 2 then
			self.state = "fight"
			if self.call and self.call:IsFullyCastable() then unit:CastAbilityNoTarget( self.call, -1 ) end
		else
			self.state = "run"
			unit:MoveToPosition( self.run_point )
		end
		return
	end

	if self.state == "run" then
		if ( unit:GetAbsOrigin() - self.run_point ):Length2D() > 120 then
			if not unit:IsMoving() then unit:MoveToPosition( self.run_point ) end
			return
		end
		self.state, self.mortal = "fight", true
		self:Note( "arrived" )
	end

	if self.phase == 1 and hp <= 60 then self:StartTelegraph( 2 ) return end
	if self.phase == 2 and hp <= 30 then self:StartTelegraph( 3 ) return end
	if self.call and self.call:IsInAbilityPhase() then return end

	local heroes = FindUnitsInRadius( unit:GetTeamNumber(), unit:GetAbsOrigin(), nil, 2500, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO, DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, false )
	local target = heroes[1]
	if not target then return end
	if self.mortal and self.hunger and self.hunger:IsFullyCastable() then
		unit:CastAbilityOnTarget( target, self.hunger, -1 )
		self:Note( "hunger" )
		return
	end
	if unit:GetAggroTarget() ~= target then unit:MoveToTargetToAttack( target ) end
end

-- 1 s warning before a phase change: boss is rooted and disarmed, a collapsing ring shows the danger zone
modifier_mcp_boss_telegraph = class({})

function modifier_mcp_boss_telegraph:IsHidden() return true end
function modifier_mcp_boss_telegraph:IsPurgable() return false end

function modifier_mcp_boss_telegraph:CheckState()
	return { [MODIFIER_STATE_ROOTED] = true, [MODIFIER_STATE_DISARMED] = true }
end

function modifier_mcp_boss_telegraph:OnCreated()
	if not IsServer() then return end
	self.pfx = ParticleManager:CreateParticle( "particles/units/heroes/hero_lina/lina_spell_light_strike_array_ring_collapse.vpcf", PATTACH_ABSORIGIN, self:GetParent() )
	-- CP1 = (radius, 0, collapse speed), same layout as mcp_giant_slam: the ring closes in exactly 1 s
	ParticleManager:SetParticleControl( self.pfx, 1, Vector( 315, 0, 1.0 / TELEGRAPH ) )
end

function modifier_mcp_boss_telegraph:OnDestroy()
	if not IsServer() then return end
	ParticleManager:DestroyParticle( self.pfx, false )
	ParticleManager:ReleaseParticleIndex( self.pfx )
end
