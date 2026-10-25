-- Stage 12 part 5: Frost Band — own item with the stock Wraith Band icon, built from Circlet + Mantle
item_mcp_frost_band = class({})
LinkLuaModifier( "modifier_item_mcp_frost_band", "items/item_mcp_frost_band", LUA_MODIFIER_MOTION_NONE )

function item_mcp_frost_band:GetIntrinsicModifierName() return "modifier_item_mcp_frost_band" end

modifier_item_mcp_frost_band = class({})
function modifier_item_mcp_frost_band:IsHidden() return true end
function modifier_item_mcp_frost_band:GetAttributes() return MODIFIER_ATTRIBUTE_MULTIPLE end
function modifier_item_mcp_frost_band:DeclareFunctions()
	return { MODIFIER_PROPERTY_STATS_INTELLECT_BONUS, MODIFIER_PROPERTY_MANA_REGEN_CONSTANT }
end
function modifier_item_mcp_frost_band:GetModifierBonusStats_Intellect() return self:GetAbility():GetSpecialValueFor( "bonus_intellect" ) end
function modifier_item_mcp_frost_band:GetModifierConstantManaRegen() return self:GetAbility():GetSpecialValueFor( "bonus_mana_regen" ) end
