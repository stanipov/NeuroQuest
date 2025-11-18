"""
Collection of Pydantic models for structured output
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


# ------------------------------- Validate and classify player's response -------------------------------
_fld_reason_desc = """"If non-game action, classify. Pick from [lore, other]"""
_fld_val_reason_desc = "Explain decision, list all identified violations (3 words max) if valid == False, empty if valid == True"

_pick_actions = ['inventory change',
                 'mental state change',
                 'physical state change',
                 'relocation',
                 'conversation',
                 'fight']
_fld_action_type_desc = f"Classify action, pick one from {_pick_actions} if valid == True else ''"

class ActionTypes(BaseModel):
    """Classification of game action"""
    action_type: str = Field(description=_fld_action_type_desc, default="")

class ValidReason(BaseModel):
    """Reason for a valid/non-valid game action"""
    reason: str = Field(description="If valid, explain in 3 words", default="")

class ValidateClassifyAction(BaseModel):
    """Validator response model"""
    is_game_action: bool =  Field(validation_alias='is_game_action', description="True/False")
    non_game_action: str = Field(validation_alias="non_game_action", description=_fld_reason_desc)
    valid: bool = Field(validation_alias='valid', description="Valid game action? True or False")
    valid_reason: List[ValidReason] = Field(description=_fld_val_reason_desc, default_factory=list)
    action_type: list[ActionTypes] = Field(description='List of actions', default_factory=list)

# ------------------------------- Description of inventory item -------------------------------
class InventoryItemDescription(BaseModel):
    """Inventory item"""
    name: str = Field(description="Object's name")
    type: str = Field(description="Type of the object")
    description: str = Field(description="Object description", default="")
    action: str = Field(description="How this object works", default="")
    strength: str = Field(description="Strength of the object", default="")

# ------------------------------- Inventory Changes -------------------------------
class InventoryItemChange(BaseModel):
    """Inventory update unit"""
    item: str = Field(validation_alias='name',
                      description="Item name")
    change_amount: int = Field(validation_alias='amount',
                               default=0,
                               description="Number of items changed")
    subject: str = Field(description="Who's inventory is changed?", default="")
    source: str = Field(description="Who provided this inventory item?", default="")

class InventoryUpdates(BaseModel):
    """All inventory updates"""
    itemUpdates: List[InventoryItemChange] = Field(default = [], description="List of inventory updates")

# ------------------------------- Player's state -------------------------------
class MentalCondition(BaseModel):
    state: str= Field(default="", description="Mental condition, 1 word")

class PhysicalCondition(BaseModel):
    state: str= Field(default="", description="Physical condition, 1 word")

class PlayerState(BaseModel):
    alive: bool = Field(default= True, description="Alive? True/False")
    physical: list[PhysicalCondition] = Field(validation_alias='physical_state',
                                     default= [],
                                     description="Physical condition")
    mental: list[MentalCondition] = Field(validation_alias='mental_state',
                                     default=[],
                                     description="Mental condition")


# ------------------------------- Player's location -------------------------------
class CurrentLocation(BaseModel):
    kingdom: str = Field(description="Current kingdom", default="")
    town: str = Field(description="Current town", default="")
    extra: str = Field(description="Fine-grained details of the current location", default="")

class DestinationLocation(BaseModel):
    kingdom: str = Field(description="Destination kingdom", default="")
    town: str = Field(description="Destination town", default="")
    extra: str = Field(description="Fine-grained details of the destination location", default="")

class PlayerLocation(BaseModel):
    current: CurrentLocation = Field(description="Current location", default=[])
    destination: DestinationLocation = Field(description="Destination", default=[])

# ------------------------------- NPC -------------------------------
class NPCResponseModel(BaseModel):
    """Response model for NPC action"""
    action: str = Field(description="Your action. 1-2 sentences", defaut = "")
    state: PlayerState = Field(description="Determine player's state", default=None)
    inventory_update: InventoryUpdates = Field(description="Detect inventory updates", default=None)
    location: PlayerLocation = Field(description="Player's current location and possibly new destination", default=None)