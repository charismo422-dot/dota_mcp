-- Test helper: counts damage taken by its parent (training dummies keep full HP, so HP cannot be compared)
modifier_mcp_damage_meter = class({})

function modifier_mcp_damage_meter:IsHidden() return true end
function modifier_mcp_damage_meter:IsPurgable() return false end
function modifier_mcp_damage_meter:RemoveOnDeath() return false end

function modifier_mcp_damage_meter:OnCreated()
	self.total = 0
end

function modifier_mcp_damage_meter:DeclareFunctions()
	return { MODIFIER_EVENT_ON_TAKEDAMAGE }
end

function modifier_mcp_damage_meter:OnTakeDamage( params )
	if params.unit == self:GetParent() then
		self.total = self.total + params.damage
	end
end
