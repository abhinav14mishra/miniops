from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.models import Incident, IncidentEvent, Alert, Service

def next_number(db: Session) -> str:
    count = db.query(Incident).count() + 1
    return f"INC-{count:05d}"

def create_or_update_incident(db: Session, alert: Alert):
    existing = db.scalar(
        select(Incident).where(
            Incident.alert_id == alert.id,
            Incident.status != "RESOLVED"
        )
    )
    # Dedupe against any active incident with the same alert/service key.
    if not existing:
        existing = db.scalar(
            select(Incident).join(Alert, Incident.alert_id == Alert.id).where(
                Alert.service_id == alert.service_id,
                Alert.dedupe_key == alert.dedupe_key,
                Incident.status != "RESOLVED"
            )
        )
    if existing:
        existing.description = alert.message
        db.add(IncidentEvent(
            incident_id=existing.id,
            event_type="ALERT_GROUPED",
            message=f"Repeated alert grouped: {alert.title}"
        ))
        db.commit()
        return existing, False

    priority = {"critical": "P1", "high": "P2", "warning": "P3", "info": "P4"}.get(alert.severity.lower(), "P3")
    incident = Incident(
        incident_number=next_number(db),
        service_id=alert.service_id,
        alert_id=alert.id,
        priority=priority,
        severity=alert.severity,
        title=alert.title,
        description=alert.message,
    )
    db.add(incident)
    db.flush()
    db.add(IncidentEvent(
        incident_id=incident.id,
        event_type="CREATED",
        message=f"Incident created from {alert.source} alert"
    ))
    db.commit()
    db.refresh(incident)
    return incident, True

def event(db, incident_id, actor_id, event_type, message):
    db.add(IncidentEvent(
        incident_id=incident_id,
        actor_user_id=actor_id,
        event_type=event_type,
        message=message
    ))
