from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class EventLogIn(BaseModel):
    """Schema for creating an event log entry (received from worker)."""
    event_id: str
    fragment_id: str  # source fragment
    counter: int
    delta: Optional[int] = None
    timestamp: str  # ISO format from source
    metadata: Optional[dict[str, Any]] = None


class EventLogOut(BaseModel):
    """Schema for returning event log entries."""
    id: int
    event_id: str
    source_fragment_id: str
    event_type: str
    payload: dict[str, Any]
    event_timestamp: datetime
    received_at: datetime

    class Config:
        orm_mode = True
