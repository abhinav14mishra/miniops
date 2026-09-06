import os, secrets
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .models import *
from .schemas import *

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
ALGORITHM = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI(title="MiniOps API", version="1.1.0")
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if not db.scalar(select(User).where(User.email=="admin@miniops.example.com")):
            db.add(User(email="admin@miniops.example.com", name="Global Admin", password_hash=pwd.hash("admin123"), role="GLOBAL_ADMIN"))
        if not db.scalar(select(User).where(User.email=="engineer@miniops.example.com")):
            db.add(User(email="engineer@miniops.example.com", name="On-call Engineer", password_hash=pwd.hash("engineer123"), role="RESPONDER"))
        db.commit()

def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        data = jwt.decode(authorization[7:], SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(User, int(data["sub"]))
    except Exception:
        user = None
    if not user or not user.is_active: raise HTTPException(401, "Invalid session")
    return user

def admin(user=Depends(current_user)):
    if user.role != "GLOBAL_ADMIN": raise HTTPException(403, "Global admin required")
    return user

def event(db, incident_id, actor, kind, message):
    db.add(IncidentEvent(incident_id=incident_id, actor_user_id=actor.id if actor else None, event_type=kind, message=message))

def audit(db, actor, action, entity_type, entity_id=None, details=""):
    db.add(AuditLog(actor_user_id=actor.id if actor else None, action=action, entity_type=entity_type, entity_id=entity_id, details=details))

@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/ready")
def ready(db: Session=Depends(get_db)):
    db.execute(select(func.count(User.id))); return {"status":"ready"}

@app.post("/api/v1/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user=db.scalar(select(User).where(User.email==body.email))
    if not user or not user.is_active or not pwd.verify(body.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
    token=jwt.encode({"sub":str(user.id)},SECRET_KEY,algorithm=ALGORITHM)
    return {"access_token":token,"token_type":"bearer","user":{"id":user.id,"email":user.email,"name":user.name,"role":user.role}}
@app.get("/api/v1/auth/me")
def me(user=Depends(current_user)): return {"id":user.id,"email":user.email,"name":user.name,"role":user.role}

@app.get("/api/v1/users")
def users(_:User=Depends(admin),db:Session=Depends(get_db)): return db.scalars(select(User).order_by(User.id)).all()
@app.post("/api/v1/users")
def create_user(body:UserCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==body.email)): raise HTTPException(409,"Email already exists")
    temporary="ChangeMe123!"; u=User(email=body.email,name=body.name,role=body.role,password_hash=pwd.hash(temporary)); db.add(u); db.flush(); audit(db,actor,"USER_CREATED","USER",u.id); db.commit()
    return {"id":u.id,"email":u.email,"name":u.name,"role":u.role,"temporary_password":temporary}
@app.post("/api/v1/users/{user_id}/disable")
def disable_user(user_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"User not found")
    if u.id==actor.id: raise HTTPException(400,"Cannot disable yourself")
    u.is_active=False; audit(db,actor,"USER_DISABLED","USER",u.id); db.commit(); return {"status":"disabled"}
@app.post("/api/v1/users/{user_id}/enable")
def enable_user(user_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"User not found")
    u.is_active=True; audit(db,actor,"USER_ENABLED","USER",u.id); db.commit(); return {"status":"enabled"}
@app.delete("/api/v1/users/{user_id}")
def delete_user(user_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"User not found")
    if u.id==actor.id: raise HTTPException(400,"Cannot remove yourself")
    db.delete(u); audit(db,actor,"USER_REMOVED","USER",user_id); db.commit(); return {"status":"removed"}

@app.get("/api/v1/teams")
def teams(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Team).order_by(Team.name)).all()
@app.post("/api/v1/teams")
def create_team(body:TeamCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(Team).where(Team.name==body.name)): raise HTTPException(409,"Team exists")
    t=Team(name=body.name,description=body.description); db.add(t); db.flush(); audit(db,actor,"TEAM_CREATED","TEAM",t.id); db.commit(); return t
@app.delete("/api/v1/teams/{team_id}")
def delete_team(team_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    t=db.get(Team,team_id)
    if not t: raise HTTPException(404,"Team not found")
    db.delete(t); audit(db,actor,"TEAM_REMOVED","TEAM",team_id); db.commit(); return {"status":"removed"}
@app.get("/api/v1/teams/{team_id}/members")
def members(team_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(TeamMember,User).join(User,User.id==TeamMember.user_id).where(TeamMember.team_id==team_id)).all()
    return [{"id":u.id,"name":u.name,"email":u.email,"role":m.role} for m,u in rows]
@app.post("/api/v1/teams/{team_id}/members")
def add_member(team_id:int,body:MemberCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(Team,team_id) or not db.get(User,body.user_id): raise HTTPException(404,"Team or user not found")
    if db.scalar(select(TeamMember).where(TeamMember.team_id==team_id,TeamMember.user_id==body.user_id)): raise HTTPException(409,"Already a member")
    db.add(TeamMember(team_id=team_id,user_id=body.user_id,role=body.role)); audit(db,actor,"MEMBER_ADDED","TEAM",team_id); db.commit(); return {"status":"added"}
@app.delete("/api/v1/teams/{team_id}/members/{user_id}")
def remove_member(team_id:int,user_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    m=db.scalar(select(TeamMember).where(TeamMember.team_id==team_id,TeamMember.user_id==user_id))
    if not m: raise HTTPException(404,"Membership not found")
    db.delete(m); audit(db,actor,"MEMBER_REMOVED","TEAM",team_id); db.commit(); return {"status":"removed"}

@app.get("/api/v1/services")
def services(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Service).order_by(Service.name)).all()
@app.post("/api/v1/services")
def create_service(body:ServiceCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(Service).where(Service.name==body.name)): raise HTTPException(409,"Service exists")
    s=Service(name=body.name,description=body.description,owner_team_id=body.owner_team_id); db.add(s); db.flush(); audit(db,actor,"SERVICE_CREATED","SERVICE",s.id); db.commit(); return s
@app.delete("/api/v1/services/{service_id}")
def delete_service(service_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    s=db.get(Service,service_id)
    if not s: raise HTTPException(404,"Service not found")
    db.delete(s); audit(db,actor,"SERVICE_REMOVED","SERVICE",service_id); db.commit(); return {"status":"removed"}
@app.get("/api/v1/services/{service_id}/routing-keys")
def routing_keys(service_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(RoutingKey).where(RoutingKey.service_id==service_id).order_by(RoutingKey.id)).all()
@app.post("/api/v1/services/{service_id}/routing-keys")
def create_key(service_id:int,body:RoutingKeyCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(Service,service_id): raise HTTPException(404,"Service not found")
    r=RoutingKey(service_id=service_id,name=body.name,key="rk_"+secrets.token_urlsafe(30)); db.add(r); db.flush(); audit(db,actor,"ROUTING_KEY_CREATED","ROUTING_KEY",r.id); db.commit(); return r
@app.post("/api/v1/routing-keys/{key_id}/rotate")
def rotate_key(key_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    r=db.get(RoutingKey,key_id)
    if not r: raise HTTPException(404,"Routing key not found")
    r.key="rk_"+secrets.token_urlsafe(30); r.is_active=True; audit(db,actor,"ROUTING_KEY_ROTATED","ROUTING_KEY",r.id); db.commit(); return r
@app.post("/api/v1/routing-keys/{key_id}/revoke")
def revoke_key(key_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    r=db.get(RoutingKey,key_id)
    if not r: raise HTTPException(404,"Routing key not found")
    r.is_active=False; audit(db,actor,"ROUTING_KEY_REVOKED","ROUTING_KEY",r.id); db.commit(); return {"status":"revoked"}

# Incident engine: dedupe open alerts onto the existing incident, mirroring the reference product's operational model.
def make_incident(db,service_id,title,description,priority,dedupe_key,user_id=None,team_id=None,actor=None):
    if dedupe_key:
        existing=db.scalar(select(Incident).where(Incident.service_id==service_id,Incident.dedupe_key==dedupe_key,Incident.status!="RESOLVED"))
        if existing:
            event(db,existing.id,actor,"ALERT_DEDUPLICATED",f"Alert grouped into INC-{existing.incident_number}"); return existing,False
    last=db.scalar(select(func.max(Incident.incident_number))) or 1000
    inc=Incident(incident_number=last+1,service_id=service_id,title=title,description=description,priority=priority,dedupe_key=dedupe_key,assigned_user_id=user_id,assigned_team_id=team_id)
    db.add(inc); db.flush(); event(db,inc.id,actor,"INCIDENT_CREATED","Incident created"); return inc,True
@app.post("/api/v1/incidents")
def create_incident(body:IncidentCreate,actor=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Service,body.service_id): raise HTTPException(404,"Service not found")
    inc,_=make_incident(db,body.service_id,body.title,body.description,body.priority,None,body.assigned_user_id,body.assigned_team_id,actor); audit(db,actor,"INCIDENT_CREATED","INCIDENT",inc.id); db.commit(); return inc
@app.post("/api/v1/alerts")
def ingest(body:AlertCreate,db:Session=Depends(get_db)):
    r=db.scalar(select(RoutingKey).where(RoutingKey.key==body.routing_key,RoutingKey.is_active==True))
    if not r: raise HTTPException(401,"Invalid routing key")
    inc,created=make_incident(db,r.service_id,body.title,body.message,"P1" if body.severity.lower() in ("critical","fatal") else "P2",body.dedupe_key); db.commit()
    return {"incident_id":inc.id,"incident_number":inc.incident_number,"created":created,"status":inc.status}
@app.get("/api/v1/incidents")
def incidents(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Incident).order_by(Incident.created_at.desc())).all()
@app.get("/api/v1/incidents/{incident_id}")
def incident(incident_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found")
    events=db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id==i.id).order_by(IncidentEvent.created_at)).all()
    notes=db.scalars(select(IncidentNote).where(IncidentNote.incident_id==i.id).order_by(IncidentNote.created_at)).all()
    return {"incident":i,"events":events,"notes":notes}
@app.post("/api/v1/incidents/{incident_id}/assign")
def assign(incident_id:int,body:AssignIn,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found")
    if body.user_id and not db.get(User,body.user_id): raise HTTPException(404,"User not found")
    if body.team_id and not db.get(Team,body.team_id): raise HTTPException(404,"Team not found")
    i.assigned_user_id=body.user_id; i.assigned_team_id=body.team_id; event(db,i.id,actor,"ASSIGNED",f"Assigned user={body.user_id} team={body.team_id}"); audit(db,actor,"INCIDENT_ASSIGNED","INCIDENT",i.id); db.commit(); return i
@app.post("/api/v1/incidents/{incident_id}/acknowledge")
def ack(incident_id:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found")
    if i.status=="RESOLVED": raise HTTPException(409,"Resolved incident must be reopened first")
    i.status="ACKNOWLEDGED"; i.acknowledged_at=datetime.now(timezone.utc); event(db,i.id,actor,"ACKNOWLEDGED","Incident acknowledged"); audit(db,actor,"INCIDENT_ACKNOWLEDGED","INCIDENT",i.id); db.commit(); return i
@app.post("/api/v1/incidents/{incident_id}/resolve")
def resolve(incident_id:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found")
    i.status="RESOLVED"; i.resolved_at=datetime.now(timezone.utc); event(db,i.id,actor,"RESOLVED","Incident resolved"); audit(db,actor,"INCIDENT_RESOLVED","INCIDENT",i.id); db.commit(); return i
@app.post("/api/v1/incidents/{incident_id}/reopen")
def reopen(incident_id:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,incident_id)
    if not i: raise HTTPException(404,"Incident not found")
    i.status="OPEN"; i.resolved_at=None; event(db,i.id,actor,"REOPENED","Incident reopened"); audit(db,actor,"INCIDENT_REOPENED","INCIDENT",i.id); db.commit(); return i
@app.post("/api/v1/incidents/{incident_id}/notes")
def add_note(incident_id:int,body:NoteCreate,actor=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Incident,incident_id): raise HTTPException(404,"Incident not found")
    n=IncidentNote(incident_id=incident_id,author_user_id=actor.id,body=body.body); db.add(n); event(db,incident_id,actor,"NOTE_ADDED","Incident note added"); db.commit(); return n

@app.get("/api/v1/policies")
def policies(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(EscalationPolicy).order_by(EscalationPolicy.name)).all()
@app.post("/api/v1/policies")
def create_policy(body:PolicyCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    p=EscalationPolicy(name=body.name,description=body.description); db.add(p); db.flush(); audit(db,actor,"POLICY_CREATED","POLICY",p.id); db.commit(); return p
@app.get("/api/v1/policies/{policy_id}/levels")
def levels(policy_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(EscalationLevel).where(EscalationLevel.policy_id==policy_id).order_by(EscalationLevel.position)).all()
@app.post("/api/v1/policies/{policy_id}/levels")
def add_level(policy_id:int,body:LevelCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(EscalationPolicy,policy_id): raise HTTPException(404,"Policy not found")
    pos=(db.scalar(select(func.max(EscalationLevel.position)).where(EscalationLevel.policy_id==policy_id)) or 0)+1
    l=EscalationLevel(policy_id=policy_id,position=pos,target_type=body.target_type,target_id=body.target_id,delay_minutes=body.delay_minutes); db.add(l); audit(db,actor,"ESCALATION_LEVEL_ADDED","POLICY",policy_id); db.commit(); return l
@app.delete("/api/v1/policies/{policy_id}")
def delete_policy(policy_id:int,actor=Depends(admin),db:Session=Depends(get_db)):
    p=db.get(EscalationPolicy,policy_id)
    if not p: raise HTTPException(404,"Policy not found")
    db.delete(p); audit(db,actor,"POLICY_REMOVED","POLICY",policy_id); db.commit(); return {"status":"removed"}

@app.get("/api/v1/schedules")
def schedules(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(OnCallSchedule).order_by(OnCallSchedule.name)).all()
@app.post("/api/v1/schedules")
def create_schedule(body:ScheduleCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not body.member_ids: raise HTTPException(400,"At least one responder is required")
    s=OnCallSchedule(name=body.name,timezone=body.timezone,rotation_type=body.rotation_type,start_hour=body.start_hour,end_hour=body.end_hour); db.add(s); db.flush()
    for pos,uid in enumerate(body.member_ids):
        if not db.get(User,uid): raise HTTPException(404,f"User {uid} not found")
        db.add(RotationMember(schedule_id=s.id,user_id=uid,position=pos))
    audit(db,actor,"SCHEDULE_CREATED","SCHEDULE",s.id); db.commit(); return s
@app.get("/api/v1/schedules/{schedule_id}/members")
def schedule_members(schedule_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(RotationMember,User).join(User,User.id==RotationMember.user_id).where(RotationMember.schedule_id==schedule_id).order_by(RotationMember.position)).all()
    return [{"id":u.id,"name":u.name,"position":m.position} for m,u in rows]
@app.get("/api/v1/schedules/{schedule_id}/overrides")
def overrides(schedule_id:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    return db.scalars(select(Override).where(Override.schedule_id==schedule_id).order_by(Override.starts_at)).all()
@app.post("/api/v1/schedules/{schedule_id}/overrides")
def create_override(schedule_id:int,body:OverrideCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(OnCallSchedule,schedule_id): raise HTTPException(404,"Schedule not found")
    try: start=datetime.fromisoformat(body.starts_at.replace("Z","+00:00")); end=datetime.fromisoformat(body.ends_at.replace("Z","+00:00"))
    except ValueError: raise HTTPException(400,"Invalid override timestamps")
    if end<=start: raise HTTPException(400,"Override end must be after start")
    o=Override(schedule_id=schedule_id,from_user_id=body.from_user_id,to_user_id=body.to_user_id,starts_at=start,ends_at=end,reason=body.reason); db.add(o); audit(db,actor,"OVERRIDE_CREATED","SCHEDULE",schedule_id); db.commit(); return o

@app.get("/api/v1/audit")
def audit_logs(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(250)).all()
