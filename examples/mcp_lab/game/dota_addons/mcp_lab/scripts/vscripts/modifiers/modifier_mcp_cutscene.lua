-- Stage 10: the player's hero during a cutscene: cannot be hurt, cannot move or attack, health bar hidden.
modifier_mcp_cutscene = class({})

function modifier_mcp_cutscene:IsHidden() return true end
function modifier_mcp_cutscene:IsPurgable() return false end

function modifier_mcp_cutscene:CheckState()
	return {
		[MODIFIER_STATE_INVULNERABLE] = true,
		[MODIFIER_STATE_COMMAND_RESTRICTED] = true,  -- blocks the player's orders only, script orders still pass
		[MODIFIER_STATE_ROOTED] = true,               -- so the hero also stays put if a script orders a move
		[MODIFIER_STATE_DISARMED] = true,
		[MODIFIER_STATE_NO_HEALTH_BAR] = true,
	}
end

-- Lives on the invisible thinker that the cutscene camera follows (CreateModifierThinker needs a modifier)
modifier_mcp_cutscene_camera = class({})

function modifier_mcp_cutscene_camera:IsHidden() return true end
function modifier_mcp_cutscene_camera:IsPurgable() return false end
