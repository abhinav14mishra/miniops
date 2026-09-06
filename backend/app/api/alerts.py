from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Alert,Service,Incident
from ..schemas import AlertCreate
from ..dependencies import get_current_user
from ..services.incident_service import create_incident
router=APIRouter(prefix="/api/v1/alerts",tags=["alerts"])
@router.post("")
def alert(p:AlertCreate,db:Session=Depends(get_db),u=Depends(get_current_user)):
    s=db.query(Service).filter(Service.name==p.service).first()
    if not s: raise HTTPException(404,"Service not found")
    key=p.dedupe_key or f"{s.name}:{p.title}"
    old=db.query(Alert).filter(Alert.dedupe_key==key).order_by(Alert.id.desc()).first()
    if old:
        i=db.query(Incident).filter(Incident.alert_id==old.id,Incident.status!="RESOLVED").first()
        if i:return {"alert":old,"incident":i,"deduplicated":True}
    a=Alert(service_id=s.id,severity=p.severity,title=p.title,message=p.message,source=p.source,dedupe_key=key)
    db.add(a);db.commit();db.refresh(a);i=create_incident(db,a,u);return {"alert":a,"incident":i,"deduplicated":False}
