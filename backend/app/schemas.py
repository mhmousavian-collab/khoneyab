from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

Amenity = Literal["parking", "elevator", "storage"]
PropertyType = Literal["apartment", "house", "villa"]
TransactionType = Literal["sale", "rent"]


class SearchCriteria(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_type: Optional[TransactionType] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    property_type: Optional[PropertyType] = None
    max_price_toman: Optional[int] = Field(default=None, ge=0)
    max_deposit_toman: Optional[int] = Field(default=None, ge=0)
    max_monthly_rent_toman: Optional[int] = Field(default=None, ge=0)
    min_area_sqm: Optional[float] = Field(default=None, ge=0)
    max_area_sqm: Optional[float] = Field(default=None, ge=0)
    bedrooms: Optional[int] = Field(default=None, ge=0, le=10)
    must_have_amenities: list[Amenity] = Field(default_factory=list)
    preferred_amenities: list[Amenity] = Field(default_factory=list)
    transit_max_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    transit_preference_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    emphasis: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    criteria: SearchCriteria = Field(default_factory=SearchCriteria)
    sort_by: Literal["relevance", "price_asc", "price_desc", "area_asc", "area_desc"] = "relevance"
    limit: int = Field(default=80, ge=1, le=200)


class InterpretRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    current_criteria: Optional[SearchCriteria] = None


class RefineRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    current_criteria: SearchCriteria


class CompareSynthesisRequest(BaseModel):
    properties: list[dict] = Field(min_length=2, max_length=3)
    user_goal: Optional[str] = None
