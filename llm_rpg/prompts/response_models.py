"""
Collection of Pydantic models for structured output
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict


# ------------------------------- Validate and classify player's response -------------------------------
_fld_reason_desc = """"If non-game action, classify. Pick from [lore, other]"""
_fld_val_reason_desc = "Explain decision, list all identified violations (3 words max) if valid == False, empty if valid == True"

_pick_actions = [
    "inventory change",
    "mental state change",
    "physical state change",
    "relocation",
    "conversation",
    "fight",
]
_fld_action_type_desc = (
    f"Classify action, pick one from {_pick_actions} if valid == True else ''"
)


class ActionTypes(BaseModel):
    """Classification of game action"""

    action_type: str = Field(description=_fld_action_type_desc, default="")


class ValidReason(BaseModel):
    """Reason for a valid/non-valid game action"""

    reason: str = Field(description="If valid, explain in 3 words", default="")


class ValidateClassifyAction(BaseModel):
    """Validator response model"""

    is_game_action: bool = Field(
        validation_alias="is_game_action", description="True/False", default=True
    )
    non_game_action: str = Field(
        validation_alias="non_game_action", description=_fld_reason_desc, default=""
    )
    valid: bool = Field(
        validation_alias="valid",
        description="Valid game action? True or False",
        default=True,
    )
    valid_reason: List[ValidReason] = Field(
        description=_fld_val_reason_desc, default_factory=list
    )
    action_type: list[ActionTypes] = Field(
        description="List of game actions if is_game_action==True", default_factory=list
    )


# ------------------------------- Inventory Changes -------------------------------
class InventoryItemChange(BaseModel):
    """Inventory update unit"""

    item: str = Field(validation_alias="name", description="Item name")
    change_amount: int = Field(
        validation_alias="amount", default=0, description="Number of items changed"
    )
    subject: str = Field(description="Who's inventory is changed?", default="")
    source: str = Field(description="Who provided this inventory item?", default="")


class InventoryUpdates(BaseModel):
    """All inventory updates"""

    itemUpdates: List[InventoryItemChange] = Field(
        default=[], description="List of inventory updates"
    )


# ------------------------------- Player's state -------------------------------
class MentalCondition(BaseModel):
    state: str = Field(default="", description="Mental condition, 1 word")


class PhysicalCondition(BaseModel):
    state: str = Field(default="", description="Physical condition, 1 word")


class PlayerState(BaseModel):
    alive: bool = Field(default=True, description="Alive? True/False")
    physical: list[PhysicalCondition] = Field(
        validation_alias="physical_state", default=[], description="Physical condition"
    )
    mental: list[MentalCondition] = Field(
        validation_alias="mental_state", default=[], description="Mental condition"
    )


# ------------------------------- Player's location -------------------------------
class CurrentLocation(BaseModel):
    kingdom: str = Field(description="Current kingdom", default="")
    town: str = Field(description="Current town", default="")
    extra: str = Field(
        description="Fine-grained details of the current location", default=""
    )


class DestinationLocation(BaseModel):
    kingdom: str = Field(description="Destination kingdom", default="")
    town: str = Field(description="Destination town", default="")
    extra: str = Field(
        description="Fine-grained details of the destination location", default=""
    )


class PlayerLocation(BaseModel):
    current: CurrentLocation | None = Field(
        description="Current location", default=None
    )
    destination: DestinationLocation | None = Field(
        description="Destination", default=None
    )


# ------------------------------- NPC -------------------------------
class NPCResponseModel(BaseModel):
    """Response model for NPC action"""

    action: str = Field(
        description="Your action. Use 3-5 sentences for complex multi-step actions",
        default="",
    )
    state: PlayerState | None = Field(
        description="Determine player's state", default=None
    )
    inventory_update: InventoryUpdates | None = Field(
        description="Detect inventory updates", default=None
    )
    location: PlayerLocation | None = Field(
        description="Player's current location and possibly new destination",
        default=None,
    )


# ------------------------------- Character Models -------------------------------


class CharacterModel(BaseModel):
    """Structured character data for players and NPCs"""

    name: str = Field(description="Character's unique name (1-3 words)", max_length=50)
    gender: str = Field(description="Character's gender", pattern="^(male|female)$")
    occupation: str = Field(
        description="Character's profession/role (e.g., warrior, researcher, magician, crook, merchant)",
        max_length=50,
    )
    age: int = Field(
        description="Character's age in years",
        ge=0,
        le=150,
    )
    biography: str = Field(
        description="Brief character backstory (1-2 sentences)", max_length=200
    )
    deeper_pains: str = Field(
        description="Character's emotional wounds or traumas (1 sentence, up to 10 words)",
        max_length=100,
    )
    deeper_desires: str = Field(
        description="Character's deepest wants and motivations (1 sentence, up to 10 words)",
        max_length=100,
    )
    goal: str = Field(
        description="Character's epic game objective - must be significant and drive the story",
        max_length=150,
    )
    physical: str = Field(
        description="Strength, dexterity, endurance as descriptive text (1 sentence)",
        max_length=100,
    )
    mental: str = Field(
        description="Intelligence and wisdom as descriptive text (1 sentence)",
        max_length=100,
    )
    communication: str = Field(
        description="Personality and persuasion ability (5 words max)", max_length=50
    )
    strengths: str = Field(
        description="Character's notable strong points (1 sentence, up to 10 words)",
        max_length=100,
    )
    weaknesses: str = Field(
        description="Character's notable weak points (1 sentence, up to 10 words)",
        max_length=100,
    )
    money: int = Field(
        description="Starting gold coins",
        ge=0,
        le=10000,
    )
    inventory: List[str] = Field(
        description="List of starting item names (functional, 1-2 words each)",
        min_length=0,
        max_length=10,
    )


# ------------------------------- World Rules -------------------------------
class WorldRulesModel(BaseModel):
    """Structured world rules organized by domain

    Each category contains 3-5 specific, actionable rules (10-15 words each)
    that define how that aspect of the world works.
    """

    MAGIC: List[str] = Field(
        description="How magic works: sources, costs, limitations, wild magic, spell mechanics. Provide 3-5 rules, each 10-15 words."
    )

    PHYSICS: List[str] = Field(
        description="Natural laws and unusual phenomena: gravity, light, time, environmental effects. Provide 3-5 rules, each 10-15 words."
    )

    SOCIETY: List[str] = Field(
        description="Social structures: governance, culture, norms, class systems, trade. Provide 3-5 rules, each 10-15 words."
    )

    GEOGRAPHY: List[str] = Field(
        description="Geographical features: climate, terrain, regions, natural hazards, resources. Provide 3-5 rules, each 10-15 words."
    )

    TECHNOLOGY: List[str] = Field(
        description="Technology level and innovations: crafting, transportation, communication, tools. Provide 3-5 rules, each 10-15 words."
    )


# ------------------------------- NPC Behavioral Rules -------------------------------
class NPCBehaviorRulesModel(BaseModel):
    """Structured behavioral rules for NPCs organized by situation type

    Each category contains 3-5 actionable directives (10-15 words each)
    that guide NPC decision-making in specific contexts.
    """

    COMBAT: List[str] = Field(
        description="Fighting style and tactical decisions: aggression level, weapon preferences, retreat conditions, ally protection. Provide 3-5 rules, each 10-15 words."
    )

    NEGOTIATION: List[str] = Field(
        description="Diplomacy and trading behavior: fairness, persuasion tactics, dealbreakers, trust-building. Provide 3-5 rules, each 10-15 words."
    )

    EXPLORATION: List[str] = Field(
        description="Discovery and investigation: risk assessment, curiosity, documentation, caution levels. Provide 3-5 rules, each 10-15 words."
    )

    SOCIAL: List[str] = Field(
        description="Interpersonal interactions: communication style, respect levels, memory of contacts, relationship building. Provide 3-5 rules, each 10-15 words."
    )

    MORAL: List[str] = Field(
        description="Ethical principles and values: dealbreakers, hierarchy of values, protection of innocents, justice. Provide 3-5 rules, each 10-15 words."
    )

    GENERAL: List[str] = Field(
        description="Overall decision-making framework: goal pursuit, strategic thinking, adaptability, long-term planning. Provide 3-5 rules, each 10-15 words."
    )


# ------------------------------- Kingdom Models -------------------------------


class KingdomData(BaseModel):
    """Single kingdom structure"""

    name: str = Field(description="Kingdom's unique name (1-3 words)", max_length=50)
    history: str = Field(
        description="Brief kingdom founding story (1 sentence, ~10 words)",
        max_length=100,
    )
    type: str = Field(
        description="Kingdom's primary characteristic: magic, militaristic, diplomatic, or technology",
        max_length=50,
    )
    location: str = Field(
        description="Geographical location within the world (up to 1 sentence)",
        max_length=100,
    )
    political_system: str = Field(
        description="Government type and structure (max 5 words)", max_length=50
    )
    national_wealth: str = Field(
        description="Economic status and resources description (max 10 words)",
        max_length=100,
    )
    international: str = Field(
        description="Relations with neighboring kingdoms (1 sentence, ~10 words)",
        max_length=100,
    )


class KingdomsModel(BaseModel):
    """Collection of kingdoms for the world"""

    kingdoms: List[KingdomData] = Field(
        description="List of all kingdoms in the fantasy world",
    )


# ------------------------------- World Description Model -------------------------------


class WorldDescriptionModel(BaseModel):
    """Structured world description"""

    name: str = Field(
        description="Unique, captivating fantasy name for the world (1 word)",
        max_length=50,
        pattern="^[A-Za-z]+$",
    )
    description: str = Field(
        description="Poetic world description capturing its essence (up to 5 sentences)",
        # max_length=600,
    )


# ------------------------------- Town Models -------------------------------


class TownData(BaseModel):
    """Single town structure"""

    name: str = Field(
        description="Town's unique, memorable name (1-2 words)", max_length=50
    )
    history: str = Field(
        description="Brief founding story or defining moment (1 sentence, ~10 words)",
        max_length=100,
    )
    location: str = Field(
        description="Geographical position within kingdom (~10 words)",
        max_length=100,
    )
    important_places: str = Field(
        description="Key landmarks, buildings, or locations (1 sentence, ~10 words)",
        max_length=100,
    )


class TownsModel(BaseModel):
    """Collection of towns for a kingdom"""

    towns: List[TownData] = Field(
        description="List of all towns in the kingdom",
    )
