from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import models
import schemas


def create_event_log(db: Session, event_in: schemas.EventLogIn) -> Optional[models.EventLog]:
    """Create an event log entry. Returns None if event_id already exists (duplicate)."""
    # Parse the timestamp from the source event
    event_timestamp = datetime.fromisoformat(event_in.timestamp.replace("Z", "+00:00"))

    # Build the full payload to store
    payload = {
        "event_id": event_in.event_id,
        "fragment_id": event_in.fragment_id,
        "counter": event_in.counter,
        "delta": event_in.delta,
        "timestamp": event_in.timestamp,
        "metadata": event_in.metadata,
    }

    event_log = models.EventLog(
        event_id=event_in.event_id,
        source_fragment_id=event_in.fragment_id,
        event_type="counter_update",
        payload=payload,
        event_timestamp=event_timestamp,
        received_at=datetime.utcnow(),
    )

    try:
        db.add(event_log)
        db.commit()
        db.refresh(event_log)
        return event_log
    except IntegrityError:
        db.rollback()
        return None  # Duplicate event_id


def get_event_logs(db: Session, skip: int = 0, limit: int = 100) -> list[models.EventLog]:
    """Get event logs, ordered by received_at descending (newest first)."""
    return (
        db.query(models.EventLog)
        .order_by(models.EventLog.received_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_event_log_by_event_id(db: Session, event_id: str) -> Optional[models.EventLog]:
    """Get a specific event log by its source event_id."""
    return db.query(models.EventLog).filter(models.EventLog.event_id == event_id).first()


def get_event_logs_by_source(db: Session, source_fragment_id: str, skip: int = 0, limit: int = 100) -> list[models.EventLog]:
    """Get event logs from a specific source fragment."""
    return (
        db.query(models.EventLog)
        .filter(models.EventLog.source_fragment_id == source_fragment_id)
        .order_by(models.EventLog.received_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
