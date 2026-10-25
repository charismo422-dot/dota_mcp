-- Stage 9: Lua AI for stock enemy heroes (no player owner). Everything is done with orders, like a player would.
-- Target: the weakest enemy hero nearby (lowest HP %), kept until a clearly weaker one shows up; never chased
-- further than LEASH from home. Retreat below 30% HP, come back at 80%. After every order the hunter "thinks"
-- for 0.3-0.6 s, so it is never a perfect bot.
-- Sven: Storm Bolt first, Warcry only in melee range, Blink to close a long gap, Faerie Fire when low.
-- Lina: keeps distance (steps back after an attack if the target is too close), Light Strike Array -> Dragon Slave
-- on the stunned target, Force Staff away from danger, Arcane Boots when mana is low.
modifier_mcp_hunter_ai = class({})

-- Stock ability/item names come from get_base_dota_definition; ranges are the KV cast ranges
local PROFILES = {
	npc_dota_hero_sven = {
		spells = {
			{ name = "sven_storm_bolt", kind = "target", range = 600 },
			{ name = "sven_warcry", kind = "none", range = 300, after = "sven_storm_bolt" },  -- bolt first, then melee
		},
	},
	npc_dota_hero_lina = {
		spells = {
			{ name = "lina_light_strike_array", kind = "point", range = 700 },
			{ name = "lina_dragon_slave", kind = "point", range = 1000, combo = "lina_light_strike_array" },  -- on the stunned target
		},
		kite = 500,  -- after an attack, step back if the target is closer than this
	},
}

local RETREAT_BELOW, RETURN_ABOVE = 30, 80
local SEARCH, LEASH = 1300, 1800
local WEAKER_BY = 20  -- switch targets only for a target this many HP % weaker

function modifier_mcp_hunter_ai:IsHidden() return true end
function modifier_mcp_hunter_ai:IsPurgable() return false end

function modifier_mcp_hunter_ai:OnCreated( kv )
	if not IsServer() then return end
	local unit = self:GetParent()
	self.home = Vector( kv.home_x or unit:GetAbsOrigin().x, kv.home_y or unit:GetAbsOrigin().y, unit:GetAbsOrigin().z )
	self.profile = PROFILES[ unit:GetUnitName() ] or { spells = {} }
	self.state, self.casts, self.items_used, self.retreats, self.returns = "hunt", {}, {}, 0, 0
	self.kites, self.kite_gain, self.combos, self.weak_picks, self.ready_at = 0, 0, 0, 0, 0
	self:StartIntervalThink( 0.25 )
end

function modifier_mcp_hunter_ai:DeclareFunctions()
	return { MODIFIER_PROPERTY_HEALTH_REGEN_PERCENTAGE, MODIFIER_EVENT_ON_ATTACK }
end

-- Retreating hunters heal quickly so that "retreat and come back" is visible within a few seconds
function modifier_mcp_hunter_ai:GetModifierHealthRegenPercentage()
	return self.state == "retreat" and 8 or 0
end

function modifier_mcp_hunter_ai:OnAttack( params )
	if not IsServer() or params.attacker ~= self:GetParent() or not self.profile.kite then return end
	local dist = ( params.target:GetAbsOrigin() - params.attacker:GetAbsOrigin() ):Length2D()
	if dist < self.profile.kite then self.kite_from = params.target end
end

-- Every order is followed by a short random "reaction" pause
function modifier_mcp_hunter_ai:Acted()
	self.ready_at = GameRules:GetGameTime() + RandomFloat( 0.3, 0.6 )
end

function modifier_mcp_hunter_ai:Ready( name )
	local item = self:GetParent():FindItemInInventory( name )
	return item and item:IsFullyCastable() and item or nil
end

function modifier_mcp_hunter_ai:UsedItem( name )
	self.items_used[ name ] = ( self.items_used[ name ] or 0 ) + 1
end

-- Force Staff pushes the caster the way it faces (SetForwardVector does not stick while the hero is turning):
-- run towards the escape point and cast it on self once facing it. Returns true if an order was given.
function modifier_mcp_hunter_ai:PushAway( towards )
	local unit = self:GetParent()
	local staff = self:Ready( "item_force_staff" )
	if not staff then return false end
	local dir = towards - unit:GetAbsOrigin()
	dir.z = 0
	if DotProduct( unit:GetForwardVector(), dir:Normalized() ) > 0.9 then
		unit:CastAbilityOnTarget( unit, staff, -1 )
		self:UsedItem( "item_force_staff" )
	else
		unit:MoveToPosition( towards )
	end
	return true
end

-- Self-help items that do not need a target; one item per think so that two orders never overwrite each other
function modifier_mcp_hunter_ai:UseSelfItems()
	local unit = self:GetParent()
	local fire = unit:GetHealthPercent() < 35 and self:Ready( "item_faerie_fire" )
	if fire then
		unit:CastAbilityNoTarget( fire, -1 )
		self:UsedItem( "item_faerie_fire" )
		return true
	end
	local boots = unit:GetManaPercent() < 50 and self:Ready( "item_arcane_boots" )
	if boots then
		unit:CastAbilityNoTarget( boots, -1 )
		self:UsedItem( "item_arcane_boots" )
		return true
	end
	return false
end

-- Weakest enemy hero within SEARCH (and inside the leash); the current target stays unless a clearly weaker one appears
function modifier_mcp_hunter_ai:PickTarget()
	local unit = self:GetParent()
	local heroes = FindUnitsInRadius( unit:GetTeamNumber(), unit:GetAbsOrigin(), nil, SEARCH, DOTA_UNIT_TARGET_TEAM_ENEMY,
		DOTA_UNIT_TARGET_HERO, DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, false )
	local best
	for _, h in ipairs( heroes ) do
		if ( h:GetAbsOrigin() - self.home ):Length2D() <= LEASH and ( not best or h:GetHealthPercent() < best:GetHealthPercent() ) then
			best = h
		end
	end
	local cur = self.target
	local cur_ok = cur and IsValidEntity( cur ) and cur:IsAlive() and ( cur:GetAbsOrigin() - self.home ):Length2D() <= LEASH
		and ( cur:GetAbsOrigin() - unit:GetAbsOrigin() ):Length2D() <= SEARCH
	if cur_ok and ( not best or best:GetHealthPercent() > cur:GetHealthPercent() - WEAKER_BY ) then return cur end
	if best and heroes[1] ~= best then self.weak_picks = self.weak_picks + 1 end  -- chose a weak target over the closest one
	return best
end

function modifier_mcp_hunter_ai:CastSpells( target, dist )
	local unit = self:GetParent()
	for _, s in ipairs( self.profile.spells ) do
		local ab = unit:FindAbilityByName( s.name )
		local ok = ab and ab:GetLevel() > 0 and ab:IsFullyCastable() and dist <= s.range
		if ok and s.after then
			local first = unit:FindAbilityByName( s.after )
			ok = not ( first and first:GetLevel() > 0 and first:IsFullyCastable() )
		end
		if ok and s.combo then
			-- wait for the stun; do not hold the spell forever if the stun spell is on a long cooldown
			local first = unit:FindAbilityByName( s.combo )
			ok = target:IsStunned() or not first or first:GetCooldownTimeRemaining() > 4
		end
		if ok then
			if s.kind == "target" then
				unit:CastAbilityOnTarget( target, ab, -1 )
			elseif s.kind == "point" then
				unit:CastAbilityOnPosition( target:GetAbsOrigin(), ab, -1 )
			else
				unit:CastAbilityNoTarget( ab, -1 )
			end
			if s.combo and target:IsStunned() then self.combos = self.combos + 1 end
			self.casts[ s.name ] = ( self.casts[ s.name ] or 0 ) + 1
			return true
		end
	end
	return false
end

function modifier_mcp_hunter_ai:OnIntervalThink()
	local unit = self:GetParent()
	if not unit:IsAlive() or unit:IsChanneling() then return end
	for _, s in ipairs( self.profile.spells ) do
		local ab = unit:FindAbilityByName( s.name )
		if ab and ab:IsInAbilityPhase() then return end
	end
	local now = GameRules:GetGameTime()
	if self:UseSelfItems() then return end

	-- Retreat/return are reflexes (no reaction pause); while retreating the hunter keeps running and does not turn back
	local hp = unit:GetHealthPercent()
	if self.state == "hunt" and hp < RETREAT_BELOW then
		self.state, self.kite_until = "retreat", nil
		self.retreats = self.retreats + 1
		unit:MoveToPosition( self.home )
		return
	end
	if self.state == "retreat" then
		if hp < RETURN_ABOVE then
			if ( unit:GetAbsOrigin() - self.home ):Length2D() > 300 and self:PushAway( self.home ) then return end
			if not unit:IsMoving() and ( unit:GetAbsOrigin() - self.home ):Length2D() > 100 then unit:MoveToPosition( self.home ) end
			return
		end
		self.state = "hunt"
		self.returns = self.returns + 1
	end

	-- Kiting: step back until the target is at kite distance again (at most 1 s)
	if self.kite_until then
		local t = self.kite_target
		local d = IsValidEntity( t ) and ( t:GetAbsOrigin() - unit:GetAbsOrigin() ):Length2D() or 0
		if now < self.kite_until and d < self.profile.kite then return end
		self.kite_gain = math.max( self.kite_gain, d - self.kite_start )
		self.kite_until = nil
	end
	if now < self.ready_at then return end

	local target = self:PickTarget()
	if target ~= self.target then
		self.target = target
		if target then self:Acted() return end  -- noticing a new target takes a moment
	end
	if not target then
		if not unit:IsMoving() and ( unit:GetAbsOrigin() - self.home ):Length2D() > 200 then
			unit:MoveToPosition( self.home )  -- leash: walk back home, do not fight on the way
			self:Acted()
		end
		return
	end

	local to_target = target:GetAbsOrigin() - unit:GetAbsOrigin()
	local dist = to_target:Length2D()
	local dir = to_target:Normalized()

	local kite = self.kite_from == target
	self.kite_from = nil
	if kite and dist < self.profile.kite then
		self.kites, self.kite_target, self.kite_start = self.kites + 1, target, dist
		self.kite_until = now + 1.0
		unit:MoveToPosition( target:GetAbsOrigin() - dir * ( self.profile.kite + 150 ) )
		return
	end

	-- Lina: an enemy right on top of her -> Force Staff away
	if self.profile.kite and dist < 250 and self:PushAway( unit:GetAbsOrigin() - dir * 600 ) then self:Acted() return end
	-- Sven: Blink closes a long gap, landing just in front of the target
	local blink = dist > 700 and self:Ready( "item_blink" )
	if blink then
		unit:CastAbilityOnPosition( target:GetAbsOrigin() - dir * 120, blink, -1 )
		self:UsedItem( "item_blink" )
		self:Acted()
		return
	end
	if self:CastSpells( target, dist ) then self:Acted() return end
	if unit:GetAggroTarget() ~= target then
		unit:MoveToTargetToAttack( target )
		self:Acted()
	end
end
