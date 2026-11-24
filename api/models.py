from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EventLog(Base):
    """Audit log for events received from other fragments via Kafka."""
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True)  # UUID from source
    source_fragment_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, default="counter_update")
    payload = Column(JSON, nullable=False)  # Store the full event payload
    event_timestamp = Column(DateTime, nullable=False)  # Timestamp from the source event
    received_at = Column(DateTime, nullable=False)  # When we received/logged it
