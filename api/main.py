from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dt_fragment_auth import FragmentAuth
from dt_fragment_auth.fastapi import protect_http

# import local modules directly (the app is copied into /app in the container build)
import database, crud, schemas, models

# Every HTTP route except /healthcheck admits only members of this fragment's
# digital twin (the user's token, from a widget), other fragments of the twin
# (the twin's Keycloak client) and this fragment's own worker (internal token).
# Deny by default: routes added later are protected too. See dt-fragment-auth.
auth = FragmentAuth.from_env()
app = FastAPI(title="Event Log API", dependencies=[Depends(protect_http(auth))])

# For development convenience only — migrations should be used in production
models.Base.metadata.create_all(bind=database.engine)


@app.get("/healthcheck")
def healthcheck():
    return {"status": "ok"}


# Event Log endpoints (internal POST for worker, public GET for reading)
@app.post("/events", response_model=schemas.EventLogOut, status_code=201, include_in_schema=False)
def create_event(payload: schemas.EventLogIn, db: Session = Depends(database.get_db)):
    """Log an event received from Kafka (called by the worker). Internal endpoint."""
    event_log = crud.create_event_log(db, payload)
    if event_log is None:
        raise HTTPException(status_code=409, detail="Event already logged (duplicate event_id)")
    return event_log


@app.get("/events", response_model=list[schemas.EventLogOut])
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source: Optional[str] = Query(None, description="Filter by source fragment ID"),
    db: Session = Depends(database.get_db),
):
    """List event logs, optionally filtered by source fragment."""
    if source:
        return crud.get_event_logs_by_source(db, source, skip=skip, limit=limit)
    return crud.get_event_logs(db, skip=skip, limit=limit)


@app.get("/events/{event_id}", response_model=schemas.EventLogOut)
def get_event(event_id: str, db: Session = Depends(database.get_db)):
    """Get a specific event by its source event_id."""
    event_log = crud.get_event_log_by_event_id(db, event_id)
    if event_log is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event_log
