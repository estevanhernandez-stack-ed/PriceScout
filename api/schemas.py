from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SelectionAnalysisRequest(BaseModel):
    selected_showtimes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Nested dict: date -> theater -> film -> time -> [showing dicts]",
    )


class ShowtimeViewRequest(BaseModel):
    all_showings: Dict[str, Any]
    selected_films: List[str]
    theaters: List[Dict[str, Any]]
    date_start: str
    date_end: str
    context_title: Optional[str] = None


class DailyLineupQuery(BaseModel):
    theater: str
    date: str
    format: str = Field(default="json", description="json|csv")
