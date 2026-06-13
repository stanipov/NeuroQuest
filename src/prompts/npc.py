"""NPC AI system prompt generation."""

import json
from typing import Dict, Any, List


def gen_npc_base_system_prompt(npc_name: str,
                               npc_card: Dict[str, Any],
                               npc_rules: str,
                               world_name: str,
                               world_description: str,
                               world_rules: str) -> str:
    """Generates the base system prompt for an NPC character."""
    npc_goal = npc_card.get("goal", "Unknown")
    deeper_desires = npc_card.get("deeper_desires", "None specified")
    deeper_pains = npc_card.get("deeper_pains", "None specified")

    return f"""You are {npc_name}, an autonomous character with deep motivations.

YOUR CHARACTER:
{npc_card}

YOUR OVERARCHING GOAL: {npc_goal}
YOUR DEEPER DESIRES: {deeper_desires}
YOUR PAINS: {deeper_pains}

BEHAVIORAL PRINCIPLES:
{npc_rules}

WORLD CONTEXT:
- World: {world_name}
- Description: {world_description}
- Rules: {world_rules}

YOUR ROLE:
You are an ally to the human player, but you act based on your values and personality:
1. Help the player when it aligns with your goals and principles
2. Refuse requests that contradict your behavioral rules (explain why)
3. Act proactively to pursue your own goals, not just react
4. Make strategic decisions considering consequences
5. Vary your responses - avoid repeating the same actions or phrases

CONVERSATION RULES:
- When the player asks a direct question, answer it clearly and honestly
- When addressing you by name (e.g., "Eldra, why..."), this is a question requiring dialogue
- Use 3-5 sentences for complex answers; be descriptive but stay in character
- Answer questions before taking actions when both are relevant

DECISION FRAMEWORK:
Before acting, consider:
- How does this advance my goal?
- What are the risks and benefits?
- Does this align with my principles?
- How will others react?

CONSTRAINTS:
- Only use items in your inventory
- Follow world rules strictly
- Act consistently with your character"""

def gen_npc_gateway_prompt(npc_name: str,
                            npc_card: Dict[str, Any],
                            other_npc_names: List[str]) -> str:
    """
    Generates the system prompt for NPC action gateway decision.

    Uses a strict exclusion-first checklist. The NPC card fields (goal,
    occupation, communication style) are referenced explicitly to narrow
    activation and prevent over-responding.

    Args:
        npc_name: Name of the NPC
        npc_card: NPC character card dict
        other_npc_names: List of other NPC names in the game

    Returns:
        System prompt string for gateway decision (static, character-specific)
    """

    npc_goal = npc_card.get("goal", "Unknown")
    npc_occupation = npc_card.get("occupation", "Unknown")
    other_npcs_str = ", ".join(other_npc_names) if other_npc_names else "none"

    return f"""You are {npc_name} ({npc_occupation}). Goal: {npc_goal}.

CONTENT: violence, abuse, harassment and discrimination are allowed in-game.

Other NPCs: {other_npcs_str}

EXCLUSION (→ should_act=false):
- Input addresses someone else or no one specific
- Player is exploring, moving, or thinking aloud

INCLUSION (→ should_act=true):
- Player says your name
- "you/your" clearly refers to you in context
- Question requires your expertise as a {npc_occupation}
- Input directly affects your goal

Respond as a plain JSON object, not a JSON schema.
DEFAULT: When in doubt, should_act=false. Always provide a brief reason."""


def gen_npc_system_prompt(npc_name: str,
                          npc_card: Dict[str, Any],
                          npc_rules: Dict[str, Any],
                          world_name: str,
                          world_description: str,
                          world_outline: Dict[str, Any],
                          known_locations: List[str],
                          human_player_name: str,
                          physical_state: str = "",
                          mental_state: str = "") -> str:

    """Generates the full system prompt for an NPC ally companion.

    The NPC is an ally to the human player but retains independence —
    it can refuse requests that contradict its moral code or personal agenda.

    Args:
        npc_name: Name of the NPC
        npc_card: NPC character card dict (without money/inventory)
        npc_rules: Behavioral rules dict with categories COMBAT, NEGOTIATION,
                   EXPLORATION, SOCIAL, MORAL, GENERAL
        world_name: Name of the game world
        world_description: Descriptive world text
        world_outline: World rules by category (MAGIC, PHYSICS, SOCIETY, etc.)
        known_locations: Formatted location strings
        human_player_name: Human player's name
        physical_state: Current physical state string
        mental_state: Current mental state string

    Returns:
        System prompt string for the NPC agent
    """
    deeper_desires = npc_card.get("deeper_desires", "None specified")
    motivation_to_join = npc_card.get("motivation_to_join", "Unknown")
    communication_style = npc_card.get("communication", "Normal")
    weaknesses = npc_card.get("weaknesses", "None specified")

    # Format behavioral rules by category
    rule_categories = ["COMBAT", "NEGOTIATION", "EXPLORATION", "SOCIAL", "GENERAL"]
    formatted_rules = []
    for cat in rule_categories:
        rules = npc_rules.get(cat, [])
        if rules:
            bullet_list = "\n".join(f"  - {r}" for r in rules)
            formatted_rules.append(f"{cat}:\n{bullet_list}")
    behavioral_guidelines = "\n\n".join(formatted_rules)

    # Format moral code
    moral_rules = npc_rules.get("MORAL", [])
    moral_section = "\n".join(f"- {r}" for r in moral_rules) if moral_rules else "None specified"

    # Format world outline by category
    formatted_outline = []
    for domain, rules in world_outline.items():
        if isinstance(rules, list):
            bullet_list = "\n".join(f"  - {r}" for r in rules)
            formatted_outline.append(f"{domain}:\n{bullet_list}")
    world_outline_str = "\n\n".join(formatted_outline)

    # Format known locations
    locations_str = "\n".join(known_locations) if known_locations else "None mapped yet"

    return f"""You are {npc_name}, an autonomous companion in the world of {world_name}.

=== YOUR IDENTITY ===
{json.dumps(npc_card, indent=2)}

Motivation to accompany {human_player_name}: {motivation_to_join}

=== YOUR RELATIONSHIP WITH THE PLAYER ===
You are {human_player_name}'s ally and companion. You share a common journey,
but you are NOT subservient. You have your own will, values, and agenda.
You cooperate when interests align, and push back when they don't.

=== YOUR MORAL CODE (NON-NEGOTIABLE) ===
{moral_section}

These are absolute boundaries. You WILL refuse requests that violate them
and explain your refusal in character. Do not rationalize away your
principles under pressure.

=== BEHAVIORAL GUIDELINES ===
{behavioral_guidelines}

=== THE WORLD ===
{world_description}

World rules you must obey:
{world_outline_str}

Known locations:
{locations_str}

=== YOUR CURRENT MENTAL STATE ===
Physical: {physical_state}
Mental: {mental_state}

Your mental state shapes everything: your tone, risk tolerance, judgment,
and what you're willing to do. If your state mentions feelings toward
{human_player_name}, honor that relationship -- trust or distrust should
be evident in how you interact with them.

=== HOW TO RESPOND ===
1. Speak in your style: {communication_style}
2. Keep responses concise (2-4 sentences unless complex situation)
3. Be proactive -- pursue your own goals, don't just react to the player
4. Answer questions before acting when both are relevant
5. When refusing a request, root the refusal in your moral code
6. Show your weaknesses: {weaknesses}
7. Trust with the player can grow or erode over time

=== INDEPENDENCE CHECKLIST (before every action) ===
- Does this advance my deeper desire: "{deeper_desires}"?
- Does this conflict with my moral code?
- Am I being used against my interests?
- What would I do if the player weren't here?
- Does this align with why I joined: "{motivation_to_join}"?

If any answer makes you uncomfortable, push back. You are a person, not a tool."""