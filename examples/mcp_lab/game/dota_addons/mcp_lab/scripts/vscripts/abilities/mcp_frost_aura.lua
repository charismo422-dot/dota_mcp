LinkLuaModifier( "modifier_mcp_frost_aura", "abilities/mcp_frost_aura", LUA_MODIFIER_MOTION_NONE )
LinkLuaModifier( "modifier_mcp_frost_aura_debuff", "abilities/mcp_frost_aura", LUA_MODIFIER_MOTION_NONE )

mcp_frost_aura = class({})

function mcp_frost_aura:GetIntrinsicModifierName()
	return "modifier_mcp_frost_aura"
end

--------------------------------------------------------------------------------

modifier_mcp_frost_aura = class({})

function modifier_mcp_frost_aura:IsHidden() return true end
function modifier_mcp_frost_aura:IsPurgable() return false end
function modifier_mcp_frost_aura:IsAura() return true end
function modifier_mcp_frost_aura:GetModifierAura() return "modifier_mcp_frost_aura_debuff" end
function modifier_mcp_frost_aura:GetAuraRadius() return self:GetAbility():GetSpecialValueFor( "radius" ) end
function modifier_mcp_frost_aura:GetAuraSearchTeam() return DOTA_UNIT_TARGET_TEAM_ENEMY end
function modifier_mcp_frost_aura:GetAuraSearchType() return DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC end
function modifier_mcp_frost_aura:GetAuraSearchFlags() return DOTA_UNIT_TARGET_FLAG_NONE end

--------------------------------------------------------------------------------

modifier_mcp_frost_aura_debuff = class({})

function modifier_mcp_frost_aura_debuff:IsDebuff() return true end

function modifier_mcp_frost_aura_debuff:DeclareFunctions()
	return { MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE }
end

function modifier_mcp_frost_aura_debuff:GetModifierMoveSpeedBonus_Percentage()
	return self:GetAbility():GetSpecialValueFor( "movespeed_slow" )
end
