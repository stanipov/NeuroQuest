"""
Action Classifier - Proposes possible action interpretations after validation passes.

This tool analyzes validated player input and generates candidate interpretations
of what the player is trying to accomplish in the game world.
"""

from typing import Dict, List, Any, Optional
import json
import logging

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.templates.tool import BaseTool
from llm_rpg.prompts.response_models import ActionProposals, _pick_actions


logger = logging.getLogger(__name__)


class ActionClassifier(BaseTool):
    """
    Proposes possible action interpretations after input validation passes.

    This tool helps disambiguate player intent by generating ranked hypotheses
    about what the player is trying to accomplish. Useful for:
    - Complex or ambiguous inputs
    - NPC response generation (understanding player intent)
    - Game state updates (knowing what triggered them)
    """

    def __init__(self, llm_client: BaseClient, lore: Dict[str, Any]):
        """
        Initialize the action classifier.

        Args:
            llm_client: LLM client for classification requests
            lore: Game lore dictionary with world context
        """
        super().__init__(llm_client, ActionProposals)

        self.lore = lore
        self._build_system_prompt()

    def _build_system_prompt(self):
        """Build the system prompt for action classification"""
        kingdoms_towns = [
            f'Kingdom "{x}" --> Towns: {", ".join(list(self.lore["towns"][x].keys()))}'
            for x in self.lore.get("towns", {})
        ]

        self.system_prompt = f"""You are an RPG Game Engine that analyzes player intent and proposes action interpretations.

YOUR TASK: Given validated game input, propose what the player is trying to accomplish.

KNOWN ACTION TYPES: {", ".join(_pick_actions)}

WORLD CONTEXT:
- Kingdoms and towns: {"\\n".join(kingdoms_towns)}
- Player character: {self.lore.get("human_player", {}).get("name", "Unknown")} ({self.lore.get("human_player", {}).get("occupation", "")})

NPCS IN WORLD:
{json.dumps({k: v.get("occupation", "") for k, v in self.lore.get("npc", {}).items()}, indent=2)}

INSTRUCTIONS:

1. **action_type**: Pick from the known action types. Use "conversation" for dialogue/questions to NPCs.

2. **target**: Who or what is the action directed at?
   - For NPC interactions: the NPC's name (e.g., "Elara Thorne")
   - For locations: the place name (e.g., "Whispering Archive")
   - For items: the item name (e.g., "memory vial")
   - Empty/null if no specific target

3. **intent**: What is the player trying to accomplish? Be concise but specific.
   Examples:
   - "Ask about Archive security layout"
   - "Trade memory vial for information"
   - "Move toward Whispering Archive entrance"
   - "Examine gravity anchor functionality"

4. **confidence**: How certain is this interpretation? (0.0-1.0)
   - High confidence: Clear, unambiguous input
   - Medium confidence: Some ambiguity but likely correct
   - Low confidence: Multiple plausible interpretations exist

5. Generate multiple proposals if the input could mean different things.
   Sort by confidence (highest first).

OUTPUT FORMAT:
- Provide 1-3 action proposals ranked by confidence
- Include a natural language summary of the primary interpretation"""

    def compile_messages(
        self,
        message: str,
        validation_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        enforce_json_output: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Build messages for the LLM.

        Args:
            message: The validated player input
            validation_result: Dict from ValidateClassifyAction model with validation results
            context: Optional dict with location, NPCs present, inventory, etc.
            enforce_json_output: Whether to add JSON schema enforcement
        """
        sys_prompt = self.system_prompt

        if enforce_json_output:
            json_schema = json.dumps(self.response_model.model_json_schema())
            sys_prompt += f"\\n\\nRespond with a JSON object that strictly follows: {json_schema}"

        # Build user message
        user_msg_parts = [f"Player input: {message}"]
        user_msg_parts.append(f"\\nValidation result:")
        user_msg_parts.append(f"  - Is game action: {validation_result.get('is_game_action', True)}")
        user_msg_parts.append(f"  - Valid: {validation_result.get('valid', True)}")
        user_msg_parts.append(f"  - Action types detected: {validation_result.get('action_types', [])}")
        user_msg_parts.append(f"  - Is NPC interaction: {validation_result.get('is_npc_interaction', False)}")

        if validation_result.get("violations"):
            user_msg_parts.append(f"  - Violations: {validation_result.get('violations')}")

        # Add context if available
        if context:
            user_msg_parts.append("\\n=== CONTEXT ===")

            if "current_location" in context:
                loc = context["current_location"]
                loc_str = f"{loc.get('town', 'Unknown')}, {loc.get('kingdom', 'Unknown Kingdom')}"
                user_msg_parts.append(f"Location: {loc_str}")

            if "npcs_at_location" in context and context["npcs_at_location"]:
                npcs = ", ".join(
                    f"{n['name']} ({n['occupation']})" for n in context["npcs_at_location"]
                )
                user_msg_parts.append(f"NPCs present: {npcs}")

            if "player_inventory" in context and context["player_inventory"]:
                inv = ", ".join(context["player_inventory"][:8])
                if len(context["player_inventory"]) > 8:
                    inv += f" (+{len(context['player_inventory']) - 8} more)"
                user_msg_parts.append(f"Inventory: {inv}")

        user_message = "\\n\\n".join(user_msg_parts)

        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_message},
        ]

    def propose_actions(
        self,
        message: str,
        validation_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        enforce_json_output: bool = False,
        **llm_kwargs,
    ) -> ActionProposals:
        """
        Analyze validated input and propose candidate action interpretations.

        Args:
            message: The validated player input string
            validation_result: Dict from ValidateClassifyAction with fields like:
                              is_game_action, valid, action_types, is_npc_interaction, violations
            context: Optional dict with dynamic context (location, NPCs, inventory)
            enforce_json_output: Whether to enforce JSON schema in response
            llm_kwargs: Additional kwargs for LLM call

        Returns:
            ActionProposals model containing ranked action interpretations

        Example return:
            {
                "proposals": [
                    {
                        "action_type": "conversation",
                        "target": "Elara Thorne",
                        "intent": "Inquire about Archive security layout",
                        "confidence": 0.85
                    },
                    {
                        "action_type": "exploration",
                        "target": "Whispering Archive",
                        "intent": "Gather information before attempting infiltration",
                        "confidence": 0.70
                    }
                ],
                "primary_interpretation": "Player is asking Elara Thorne about the security layout of the Whispering Archive, likely gathering intel for their planned infiltration."
            }
        """
        logger.info("Classifying player action intent")

        messages = self.compile_messages(
            message, validation_result, context, enforce_json_output
        )

        return self.submit_messages(messages, **llm_kwargs)


# Convenience function for quick classification without instantiating the class
def classify_action(
    llm_client: BaseClient,
    lore: Dict[str, Any],
    message: str,
    validation_result: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> ActionProposals:
    """
    Quick action classification without creating an ActionClassifier instance.

    Args:
        llm_client: LLM client
        lore: Game lore dictionary
        message: Player input to classify
        validation_result: Validation results dict
        context: Optional context dict

    Returns:
        ActionProposals model
    """
    classifier = ActionClassifier(llm_client, lore)
    return classifier.propose_actions(message, validation_result, context)
