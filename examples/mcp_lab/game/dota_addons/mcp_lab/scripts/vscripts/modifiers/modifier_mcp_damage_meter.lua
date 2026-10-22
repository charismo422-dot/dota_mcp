-- Test helper: counts damage taken by its parent (training dummies keep full HP, so HP cannot be compared)
-- and reports every hit to Panorama for floating damage numbers.
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
		if IsServer() and params.damage >= 1 then
			CustomGameEventManager:Send_ServerToAllClients( "mcp_lab_dmg", {
				ent = params.unit:entindex(),
				amount = math.floor( params.damage + 0.5 ),
				dtype = params.damage_type,
			} )
		end
	end
end
