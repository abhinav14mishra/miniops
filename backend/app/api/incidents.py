from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Incident,IncidentEvent,User,Team
from ..schemas import Assignment,IncidentOut,EventOut
from ..dependencies import get_current_user
from ..services.incident_service import add_event
from ..models.models import now
router=APIRouter(prefix="/api/v1/incidents",tags=["incidents"])
def out(db,i):
    es=db.query(IncidentEvent).filter(IncidentEvent.incident_id==i.id).order_by(IncidentEvent.id).all()
    return IncidentOut(**{k:getattr(i,k) for k in ["id","incident_number","service_id","severity","status","title","description","assigned_to_user","assigned_to_team","created_at","acknowledged_at","resolved_at"]},events=[EventOut.model_validate(e) for e in es])
@router.get("",response_model=list[IncidentOut])
def listing(db:Session=Depends(get_db),u=Depends(get_current_user)): return [out(db,i) for i in db.query(Incident).order_by(Incident.id.desc()).all()]
@router.get("/{iid}",response_model=IncidentOut)
def get(iid:int,db:Session=Depends(get_db),u=Depends(get_current_user)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,"Incident not found")
    return out(db,i)
@router.post("/{iid}/assign",response_model=IncidentOut)
def assign(iid:int,p:Assignment,db:Session=Depends(get_db),u=Depends(get_current_user)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,"Incident not found")
    if p.user_id and not db.get(User,p.user_id): raise HTTPException(404,"User not found")
    if p.team_id and not db.get(Team,p.team_id): raise HTTPException(404,"Team not found")
    i.assigned_to_user=p.user_id;i.assigned_to_team=p.team_id
    add_event(db,i,u,"assigned",f"Assigned to user={p.user_id}, team={p.team_id}");db.commit();db.refresh(i);return out(db,i)
@router.post("/{iid}/acknowledge",response_model=IncidentOut)
def ack(iid:int,db:Session=Depends(get_db),u=Depends(get_current_user)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,"Incident not found")
    if i.status=="RESOLVED": raise HTTPException(409,"Incident already resolved")
    i.status="ACKNOWLEDGED";i.acknowledged_at=now();add_event(db,i,u,"acknowledged",f"{u.name} acknowledged the incident");db.commit();db.refresh(i);return out(db,i)
@router.post("/{iid}/resolve",response_model=IncidentOut)
def resolve(iid:int,db:Session=Depends(get_db),u=Depends(get_current_user)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,"Incident not found")
    i.status="RESOLVED";i.resolved_at=now();add_event(db,i,u,"resolved",f"{u.name} resolved the incident");db.commit();db.refresh(i);return out(db,i)
