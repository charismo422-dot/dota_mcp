-- Reward from the Rift Keeper dialog: movement speed boost with a visible aura
modifier_mcp_rift_blessing = class({})

function modifier_mcp_rift_blessing:IsPurgable() return false end
function modifier_mcp_rift_blessing:GetTexture() return "item_mcp_void_shard" end

function modifier_mcp_rift_blessing:DeclareFunctions()
	return { MODIFIER_PROPERTY_MOVESPEED_BONUS_PERCENTAGE }
end

function modifier_mcp_rift_blessing:GetModifierMoveSpeedBonus_Percentage()
	return 25
end

function modifier_mcp_rift_blessing:GetEffectName()
	return "particles/generic_gameplay/rune_haste_owner.vpcf"
end

function modifier_mcp_rift_blessing:GetEffectAttachType()
	return PATTACH_ABSORIGIN_FOLLOW
end
