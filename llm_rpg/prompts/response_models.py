"""
Collection of Pydantic models for structured output
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


# ------------------------------- Validate player's response -------------------------------
class ValidAction(BaseModel):
    """Validator response model"""
    valid: bool = Field(validation_alias='valid', description="Identify if player's actions are valid. Allowed values: True or False")
    valid_reason: str = Field(description="Explain your decision on validity of player's action. Your response is a \
list all identified violations (1-3 words for each) if valid == False, empty string if valid == True")


# ------------------------------- Inventory item base model -------------------------------
class InventoryItem(BaseModel):
    item: str = Field(validation_alias='name',
                      description="Item name")
    change_amount: int = Field(validation_alias='amount',
                               default=0,
                               description="Number of items changed")

class Inventory(BaseModel):
    itemUpdates: List[InventoryItem]

# Player's state
class PlayerState(BaseModel):
    physical: Optional[str] = Field(validation_alias='physical_state',
                                     default="",
                                     description="Physical state of the character, e.g. fresh, tired, etc.")
    mental: Optional[str] = Field(validation_alias='mental_state',
                                     default="",
                                     description="Mental state of the character, e.g. aware, rested, etc.")
    itemUpdates: List[InventoryItem]
    kingdom: Optional[str] = ""
    town: Optional[str] = ""