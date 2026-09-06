from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import secrets
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_token
from app.db.session import Base, engine, get_db
from app.models.models import User, Team, TeamMember, Service, Integration, Alert, Incident, IncidentEvent, IncidentNote, Invitation, AuditLog
from app.schemas.schemas import *
from app.api.deps import current_user, admin_only
from app.services.incidents import create_or_update_incident, event

app = FastAPI(title="MiniOps API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        if not db.scalar(select(User).where(User.email == "admin@miniops.example.com")):
            db.add_all([
                User(email="admin@miniops.example.com", name="Global Admin", role="GLOBAL_ADMIN", password_hash=hash_password("admin123")),
                User(email="engineer@miniops.example.com", name="On-call Engineer", role="RESPONDER", password_hash=hash_password("engineer123")),
            ])
            db.commit()
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(func.count(User.id)))
    return {"status": "ready"}

@app.post("/api/v1/auth/login")
def login(body: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_token(user.id, settings.secret_key), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}

@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

@app.get("/api/v1/users")
def users(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()

@app.post("/api/v1/users/invite")
def invite(body: InviteCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    temp = "ChangeMe123!"
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(409, "User already exists")
    user = User(email=body.email, name=body.name, role=body.role, password_hash=hash_password(temp))
    db.add(user)
    db.flush()
    db.add(Invitation(email=body.email, name=body.name, role=body.role, temporary_password=temp))
    db.add(AuditLog(actor_user_id=admin.id, action="INVITE_USER", resource_type="USER", resource_id=str(user.id), details=body.email))
    db.commit()
    return {"user_id": user.id, "temporary_password": temp}

@app.get("/api/v1/teams")
def teams(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Team).order_by(Team.name)).all()

@app.post("/api/v1/teams")
def create_team(body: TeamCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    team = Team(name=body.name, description=body.description)
    db.add(team); db.flush()
    db.add(AuditLog(actor_user_id=admin.id, action="CREATE_TEAM", resource_type="TEAM", resource_id=str(team.id)))
    db.commit(); db.refresh(team)
    return team

@app.get("/api/v1/teams/{team_id}/members")
def team_members(team_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(TeamMember, User).join(User, User.id == TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "role": m.role} for m, u in rows]

@app.post("/api/v1/teams/{team_id}/members")
def add_member(team_id: int, body: MemberCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if not db.get(Team, team_id) or not db.get(User, body.user_id):
        raise HTTPException(404, "Team or user not found")
    db.add(TeamMember(team_id=team_id, user_id=body.user_id, role=body.role))
    db.commit()
    return {"status": "added"}

@app.get("/api/v1/services")
def services(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Service).order_by(Service.name)).all()

@app.post("/api/v1/services")
def create_service(body: ServiceCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    service = Service(name=body.name, description=body.description, team_id=body.team_id)
    db.add(service); db.commit(); db.refresh(service)
    return service

@app.post("/api/v1/services/{service_id}/integrations")
def create_integration(service_id: int, body: IntegrationCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if not db.get(Service, service_id):
        raise HTTPException(404, "Service not found")
    key = "mops_" + secrets.token_urlsafe(32)
    item = Integration(service_id=service_id, name=body.name, api_key=key)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "name": item.name, "api_key": item.api_key}

@app.post("/api/v1/integrations/{api_key}/alerts")
def ingest_alert(api_key: str, body: AlertCreate, db: Session = Depends(get_db)):
    integration = db.scalar(select(Integration).where(Integration.api_key == api_key, Integration.enabled == True))
    if not integration:
        raise HTTPException(401, "Invalid integration key")
    alert = Alert(service_id=integration.service_id, integration_id=integration.id, **body.model_dump())
    db.add(alert); db.flush()
    incident, created = create_or_update_incident(db, alert)
    return {"incident": incident.incident_number, "incident_id": incident.id, "created": created}

@app.get("/api/v1/incidents")
def incidents(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Incident).order_by(Incident.created_at.desc())).all()

@app.get("/api/v1/incidents/{incident_id}")
def incident_detail(incident_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at)).all()
    notes = db.scalars(select(IncidentNote).where(IncidentNote.incident_id == incident_id).order_by(IncidentNote.created_at)).all()
    return {"incident": incident, "events": events, "notes": notes}

@app.post("/api/v1/incidents/{incident_id}/assign")
def assign(incident_id: int, body: AssignRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    if body.user_id is None and body.team_id is None:
        raise HTTPException(400, "user_id or team_id required")
    incident.assigned_to_user = body.user_id
    incident.assigned_to_team = body.team_id
    target = f"user {body.user_id}" if body.user_id else f"team {body.team_id}"
    event(db, incident.id, user.id, "ASSIGNED", f"Assigned to {target}")
    db.commit()
    return {"status": "assigned"}

@app.post("/api/v1/incidents/{incident_id}/acknowledge")
def acknowledge(incident_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    if incident.status == "RESOLVED": raise HTTPException(409, "Incident is resolved")
    incident.status = "ACKNOWLEDGED"
    incident.acknowledged_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    event(db, incident.id, user.id, "ACKNOWLEDGED", f"Acknowledged by {user.name}")
    db.commit()
    return {"status": "acknowledged"}

@app.post("/api/v1/incidents/{incident_id}/resolve")
def resolve(incident_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    incident.status = "RESOLVED"
    incident.resolved_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    event(db, incident.id, user.id, "RESOLVED", f"Resolved by {user.name}")
    db.commit()
    return {"status": "resolved"}

@app.post("/api/v1/incidents/{incident_id}/notes")
def add_note(incident_id: int, body: NoteCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(Incident, incident_id): raise HTTPException(404, "Incident not found")
    note = IncidentNote(incident_id=incident_id, author_user_id=user.id, body=body.body)
    db.add(note)
    event(db, incident_id, user.id, "NOTE_ADDED", "Incident note added")
    db.commit()
    return {"status": "added"}

@app.get("/api/v1/audit")
def audit(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())).all()
