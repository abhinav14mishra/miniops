from typing import Optional
from sqlalchemy.orm import Session
from ..models import Incident,IncidentEvent,Alert,User
def create_incident(db:Session,alert:Alert,actor:Optional[User]=None):
    count=db.query(Incident).count()+1
    i=Incident(incident_number=f"INC-{count:04d}",service_id=alert.service_id,alert_id=alert.id,severity=alert.severity,status="OPEN",title=alert.title,description=alert.message)
    db.add(i); db.flush()
    db.add(IncidentEvent(incident_id=i.id,actor_user_id=actor.id if actor else None,event_type="created",message=f"Incident created from {alert.source} alert"))
    db.commit(); db.refresh(i); return i
def add_event(db,i,actor,event_type,message):
    db.add(IncidentEvent(incident_id=i.id,actor_user_id=actor.id if actor else None,event_type=event_type,message=message))
