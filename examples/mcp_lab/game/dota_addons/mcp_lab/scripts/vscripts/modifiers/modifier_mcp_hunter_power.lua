-- Stage 9: hunters' power. One stack per power level (grows by timer and when a hunter falls)
modifier_mcp_hunter_power = class({})

function modifier_mcp_hunter_power:IsHidden() return false end
function modifier_mcp_hunter_power:IsPurgable() return false end
function modifier_mcp_hunter_power:IsDebuff() return false end
function modifier_mcp_hunter_power:GetTexture() return "lina_fiery_soul" end

function modifier_mcp_hunter_power:DeclareFunctions()
	return { MODIFIER_PROPERTY_DAMAGEOUTGOING_PERCENTAGE, MODIFIER_PROPERTY_ATTACKSPEED_BONUS_CONSTANT, MODIFIER_PROPERTY_MODEL_SCALE }
end

function modifier_mcp_hunter_power:GetModifierDamageOutgoing_Percentage() return 10 * self:GetStackCount() end
function modifier_mcp_hunter_power:GetModifierAttackSpeedBonus_Constant() return 10 * self:GetStackCount() end
function modifier_mcp_hunter_power:GetModifierModelScale() return 4 * self:GetStackCount() end
