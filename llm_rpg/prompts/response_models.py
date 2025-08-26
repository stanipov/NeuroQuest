"""
Collection of Pydantic models for structured output
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


# ------------------------------- Validate and classify player's response -------------------------------
_fld_reason_desc = """"Explain decision, 1-2 words. Pick from [lore, other, game]"""
_fld_val_reason_desc = "Explain your decision and list all identified violations (3 words for each max) if valid == False, empty if valid == True"

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
    valid: bool = Field(validation_alias='valid', description="Valid game action? True or False")
    valid_reason: List[ValidReason] = Field(description=_fld_val_reason_desc, default=[])
    action_type: list[ActionTypes] = Field(description='List of actions', default=[])

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

class InventoryUpdates(BaseModel):
    """All inventory updates"""
    itemUpdates: List[InventoryItemChange] = Field(default = [], description="List of inventory updates")

# ------------------------------- Player's state -------------------------------
class PlayerState(BaseModel):
    physical: Optional[str] = Field(validation_alias='physical_state',
                                     default="",
                                     description="Physical state of the character, e.g. fresh, tired, etc.")
    mental: Optional[str] = Field(validation_alias='mental_state',
                                     default="",
                                     description="Mental state of the character, e.g. aware, rested, etc.")
    itemUpdates: List[InventoryItemDescription]
    kingdom: Optional[str] = ""
    town: Optional[str] = ""