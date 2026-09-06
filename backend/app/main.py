import os,secrets,json
from datetime import datetime,timezone,timedelta
from fastapi import FastAPI,Depends,HTTPException,Header
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select,func,or_,delete
from sqlalchemy.orm import Session
from .db import Base,engine,get_db
from .models import *
from .schemas import *
SECRET_KEY=os.getenv('SECRET_KEY','dev-only-change-me'); ALGORITHM='HS256'; pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
app=FastAPI(title='MiniOps API',version='2.0.0')
origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','); app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

def token_for(u): return jwt.encode({'sub':str(u.id),'exp':datetime.now(timezone.utc)+timedelta(hours=12)},SECRET_KEY,algorithm=ALGORITHM)
def current_user(authorization:str=Header(default=''),db:Session=Depends(get_db)):
    if not authorization.startswith('Bearer '): raise HTTPException(401,'Authentication required')
    try: uid=int(jwt.decode(authorization[7:],SECRET_KEY,algorithms=[ALGORITHM])['sub']); u=db.get(User,uid)
    except Exception: u=None
    if not u or not u.is_active: raise HTTPException(401,'Invalid session')
    return u
def admin(u=Depends(current_user)):
    if u.role!='GLOBAL_ADMIN': raise HTTPException(403,'Global admin required')
    return u
def audit(db,actor,action,etype,eid=None,details=''): db.add(AuditLog(actor_user_id=actor.id if actor else None,action=action,entity_type=etype,entity_id=eid,details=details))
def event(db,iid,actor,kind,msg): db.add(IncidentEvent(incident_id=iid,actor_user_id=actor.id if actor else None,event_type=kind,message=msg))
def serialize_user(u): return {'id':u.id,'email':u.email,'name':u.name,'role':u.role,'is_active':u.is_active,'created_at':u.created_at}
def oncall_user(db,schedule_id,at=None):
    at=at or datetime.now(timezone.utc); members=db.scalars(select(RotationMember).where(RotationMember.schedule_id==schedule_id).order_by(RotationMember.position)).all()
    if not members:return None
    o=db.scalar(select(Override).where(Override.schedule_id==schedule_id,Override.starts_at<=at,Override.ends_at>=at).order_by(Override.starts_at.desc()))
    if o:return db.get(User,o.to_user_id)
    s=db.get(OnCallSchedule,schedule_id); anchor=at.date().toordinal(); idx=(anchor if s.rotation_type=='DAILY' else anchor//7 if s.rotation_type=='WEEKLY' else anchor//28)%len(members)
    return db.get(User,members[idx].user_id)
def targets(db,level):
    if level.target_type=='USER': return [db.get(User,level.target_id)]
    if level.target_type=='TEAM':
        return list(db.scalars(select(User).join(TeamMember,TeamMember.user_id==User.id).where(TeamMember.team_id==level.target_id,User.is_active==True)).all())
    u=oncall_user(db,level.target_id); return [u] if u else []
def create_incident(db,service_id,title,description,priority,dedupe,actor=None,user_id=None,team_id=None):
    if dedupe:
        existing=db.scalar(select(Incident).where(Incident.service_id==service_id,Incident.dedupe_key==dedupe,Incident.status!='RESOLVED').order_by(Incident.created_at.desc()))
        if existing: event(db,existing.id,actor,'ALERT_DEDUPLICATED',f'Alert grouped into INC-{existing.incident_number}'); return existing,False
    svc=db.get(Service,service_id); last=db.scalar(select(func.max(Incident.incident_number))) or 1000
    inc=Incident(incident_number=last+1,service_id=service_id,title=title,description=description,priority=priority,dedupe_key=dedupe,assigned_user_id=user_id,assigned_team_id=team_id,escalation_policy_id=svc.escalation_policy_id if svc else None)
    db.add(inc); db.flush(); event(db,inc.id,actor,'INCIDENT_CREATED','Incident created')
    if inc.escalation_policy_id:
        levels=db.scalars(select(EscalationLevel).where(EscalationLevel.policy_id==inc.escalation_policy_id).order_by(EscalationLevel.position)).all()
        if levels:
            ts=targets(db,levels[0]); ts=[x for x in ts if x and x.is_active]
            if ts and not inc.assigned_user_id: inc.assigned_user_id=ts[0].id; event(db,inc.id,actor,'ESCALATED',f'Assigned to {ts[0].name}')
            inc.next_escalation_at=datetime.now(timezone.utc)+timedelta(minutes=levels[0].delay_minutes)
    return inc,True
@app.on_event('startup')
def startup():
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if not db.scalar(select(User).where(User.email=='admin@miniops.example.com')): db.add(User(email='admin@miniops.example.com',name='Global Admin',password_hash=pwd.hash('admin123'),role='GLOBAL_ADMIN'))
        if not db.scalar(select(User).where(User.email=='engineer@miniops.example.com')): db.add(User(email='engineer@miniops.example.com',name='On-call Engineer',password_hash=pwd.hash('engineer123'),role='RESPONDER'))
        db.commit()
@app.get('/health')
def health(): return {'status':'ok','service':'miniops-api'}
@app.get('/ready')
def ready(db:Session=Depends(get_db)): db.execute(select(func.count(User.id))); return {'status':'ready'}
@app.post('/api/v1/auth/login')
def login(b:LoginIn,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==b.email))
    if not u or not u.is_active or not pwd.verify(b.password,u.password_hash): raise HTTPException(401,'Invalid email or password')
    return {'access_token':token_for(u),'token_type':'bearer','user':serialize_user(u)}
@app.get('/api/v1/auth/me')
def me(u=Depends(current_user)): return serialize_user(u)
@app.get('/api/v1/users')
def users(_:User=Depends(admin),db:Session=Depends(get_db)): return [serialize_user(x) for x in db.scalars(select(User).order_by(User.name)).all()]
@app.post('/api/v1/users')
def create_user(b:UserCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==b.email)): raise HTTPException(409,'Email already exists')
    password=b.password or secrets.token_urlsafe(10); u=User(email=b.email,name=b.name,password_hash=pwd.hash(password),role=b.role); db.add(u); db.flush(); audit(db,actor,'USER_CREATED','USER',u.id); db.commit(); return {'user':serialize_user(u),'temporary_password':password if not b.password else None}
@app.post('/api/v1/users/{uid}/disable')
def disable(uid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    if u.id==actor.id: raise HTTPException(400,'You cannot disable yourself')
    u.is_active=False; audit(db,actor,'USER_DISABLED','USER',uid); db.commit(); return serialize_user(u)
@app.post('/api/v1/users/{uid}/enable')
def enable(uid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    u.is_active=True; audit(db,actor,'USER_ENABLED','USER',uid); db.commit(); return serialize_user(u)
@app.delete('/api/v1/users/{uid}')
def delete_user(uid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,'User not found')
    if u.id==actor.id: raise HTTPException(400,'You cannot remove yourself')
    u.is_active=False; u.email=f'deleted+{u.id}@invalid.local'; audit(db,actor,'USER_REMOVED','USER',uid); db.commit(); return {'status':'removed'}
@app.post('/api/v1/users/invite')
def invite(b:InvitationCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    inv=Invitation(email=b.email,name=b.name,role=b.role,token=secrets.token_urlsafe(32),expires_at=datetime.now(timezone.utc)+timedelta(days=7)); db.add(inv); audit(db,actor,'INVITATION_CREATED','INVITATION',None,b.email); db.commit(); return {'id':inv.id,'email':inv.email,'token':inv.token,'expires_at':inv.expires_at}
@app.get('/api/v1/invitations')
def invitations(_:User=Depends(admin),db:Session=Depends(get_db)): return db.scalars(select(Invitation).order_by(Invitation.created_at.desc())).all()
@app.post('/api/v1/invitations/{iid}/accept')
def accept_invite(iid:int,db:Session=Depends(get_db)):
    inv=db.get(Invitation,iid)
    if not inv or inv.status!='PENDING': raise HTTPException(404,'Invitation not found')
    if inv.expires_at<datetime.now(timezone.utc): raise HTTPException(410,'Invitation expired')
    if db.scalar(select(User).where(User.email==inv.email)): raise HTTPException(409,'User already exists')
    temp=secrets.token_urlsafe(10); u=User(email=inv.email,name=inv.name,password_hash=pwd.hash(temp),role=inv.role); db.add(u); inv.status='ACCEPTED'; db.commit(); return {'user':serialize_user(u),'temporary_password':temp}
@app.get('/api/v1/teams')
def teams(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Team).order_by(Team.name)).all()
@app.post('/api/v1/teams')
def create_team(b:TeamCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(Team).where(Team.name==b.name)): raise HTTPException(409,'Team already exists')
    t=Team(name=b.name,description=b.description); db.add(t); db.flush(); audit(db,actor,'TEAM_CREATED','TEAM',t.id); db.commit(); return t
@app.delete('/api/v1/teams/{tid}')
def delete_team(tid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    t=db.get(Team,tid)
    if not t: raise HTTPException(404,'Team not found')
    db.delete(t); audit(db,actor,'TEAM_REMOVED','TEAM',tid); db.commit(); return {'status':'removed'}
@app.get('/api/v1/teams/{tid}/members')
def team_members(tid:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(TeamMember,User).join(User,User.id==TeamMember.user_id).where(TeamMember.team_id==tid)).all(); return [{'id':u.id,'name':u.name,'email':u.email,'role':m.role,'is_active':u.is_active} for m,u in rows]
@app.post('/api/v1/teams/{tid}/members')
def add_member(tid:int,b:MemberCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(Team,tid) or not db.get(User,b.user_id): raise HTTPException(404,'Team or user not found')
    if db.scalar(select(TeamMember).where(TeamMember.team_id==tid,TeamMember.user_id==b.user_id)): raise HTTPException(409,'Already a member')
    m=TeamMember(team_id=tid,user_id=b.user_id,role=b.role); db.add(m); audit(db,actor,'TEAM_MEMBER_ADDED','TEAM',tid,str(b.user_id)); db.commit(); return m
@app.delete('/api/v1/teams/{tid}/members/{uid}')
def remove_member(tid:int,uid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    m=db.scalar(select(TeamMember).where(TeamMember.team_id==tid,TeamMember.user_id==uid))
    if not m: raise HTTPException(404,'Membership not found')
    db.delete(m); audit(db,actor,'TEAM_MEMBER_REMOVED','TEAM',tid,str(uid)); db.commit(); return {'status':'removed'}
@app.get('/api/v1/services')
def services(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Service).order_by(Service.name)).all()
@app.post('/api/v1/services')
def create_service(b:ServiceCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(Service).where(Service.name==b.name)): raise HTTPException(409,'Service already exists')
    s=Service(**b.model_dump()); db.add(s); db.flush(); audit(db,actor,'SERVICE_CREATED','SERVICE',s.id); db.commit(); return s
@app.post('/api/v1/services/{sid}/maintenance')
def maintenance(sid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    s=db.get(Service,sid)
    if not s: raise HTTPException(404,'Service not found')
    s.maintenance=not s.maintenance; audit(db,actor,'SERVICE_MAINTENANCE_TOGGLED','SERVICE',sid,str(s.maintenance)); db.commit(); return s
@app.get('/api/v1/services/{sid}/routing-keys')
def routing_keys(sid:int, _:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(RoutingKey).where(RoutingKey.service_id==sid).order_by(RoutingKey.created_at.desc())).all()
@app.post('/api/v1/services/{sid}/routing-keys')
def create_key(sid:int,b:RoutingKeyCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(Service,sid): raise HTTPException(404,'Service not found')
    r=RoutingKey(service_id=sid,name=b.name,key='rk_'+secrets.token_urlsafe(30)); db.add(r); db.flush(); audit(db,actor,'ROUTING_KEY_CREATED','ROUTING_KEY',r.id); db.commit(); return r
@app.post('/api/v1/routing-keys/{kid}/rotate')
def rotate_key(kid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    r=db.get(RoutingKey,kid)
    if not r: raise HTTPException(404,'Routing key not found')
    r.key='rk_'+secrets.token_urlsafe(30); r.is_active=True; audit(db,actor,'ROUTING_KEY_ROTATED','ROUTING_KEY',kid); db.commit(); return r
@app.post('/api/v1/routing-keys/{kid}/revoke')
def revoke_key(kid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    r=db.get(RoutingKey,kid)
    if not r: raise HTTPException(404,'Routing key not found')
    r.is_active=False; audit(db,actor,'ROUTING_KEY_REVOKED','ROUTING_KEY',kid); db.commit(); return {'status':'revoked'}
@app.post('/api/v1/incidents')
def create_inc(b:IncidentCreate,actor=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Service,b.service_id): raise HTTPException(404,'Service not found')
    i,_=create_incident(db,b.service_id,b.title,b.description,b.priority,None,actor,b.assigned_user_id,b.assigned_team_id); audit(db,actor,'INCIDENT_CREATED','INCIDENT',i.id); db.commit(); return i
@app.post('/api/v1/alerts')
def ingest(b:AlertCreate,db:Session=Depends(get_db)):
    r=db.scalar(select(RoutingKey).where(RoutingKey.key==b.routing_key,RoutingKey.is_active==True));
    if not r: raise HTTPException(401,'Invalid routing key')
    svc=db.get(Service,r.service_id)
    if svc and svc.maintenance: return {'created':False,'suppressed':True,'reason':'service in maintenance'}
    a=Alert(service_id=r.service_id,severity=b.severity,title=b.title,message=b.message,source=b.source,dedupe_key=b.dedupe_key,payload=json.dumps(b.payload)); db.add(a)
    pr='P1' if b.severity.lower() in ('critical','fatal') else 'P2'; i,created=create_incident(db,r.service_id,b.title,b.message,pr,b.dedupe_key,None); db.commit(); return {'incident_id':i.id,'incident_number':i.incident_number,'created':created,'status':i.status}
@app.get('/api/v1/incidents')
def incidents(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Incident).order_by(Incident.created_at.desc())).all()
@app.get('/api/v1/incidents/{iid}')
def incident(iid:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,'Incident not found')
    return {'incident':i,'events':db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id==iid).order_by(IncidentEvent.created_at)).all(),'notes':db.scalars(select(IncidentNote).where(IncidentNote.incident_id==iid).order_by(IncidentNote.created_at)).all()}
@app.post('/api/v1/incidents/{iid}/assign')
def assign(iid:int,b:AssignIn,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,'Incident not found')
    if b.user_id and not db.get(User,b.user_id): raise HTTPException(404,'User not found')
    if b.team_id and not db.get(Team,b.team_id): raise HTTPException(404,'Team not found')
    i.assigned_user_id=b.user_id; i.assigned_team_id=b.team_id; event(db,i.id,actor,'ASSIGNED',f'Assigned user={b.user_id} team={b.team_id}'); audit(db,actor,'INCIDENT_ASSIGNED','INCIDENT',iid); db.commit(); return i
@app.post('/api/v1/incidents/{iid}/acknowledge')
def ack(iid:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,'Incident not found')
    if i.status=='RESOLVED': raise HTTPException(409,'Reopen before acknowledging')
    i.status='ACKNOWLEDGED'; i.acknowledged_at=datetime.now(timezone.utc); i.next_escalation_at=None; i.assigned_user_id=i.assigned_user_id or actor.id; event(db,i.id,actor,'ACKNOWLEDGED','Incident acknowledged'); audit(db,actor,'INCIDENT_ACKNOWLEDGED','INCIDENT',iid); db.commit(); return i
@app.post('/api/v1/incidents/{iid}/resolve')
def resolve(iid:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,'Incident not found')
    i.status='RESOLVED'; i.resolved_at=datetime.now(timezone.utc); i.next_escalation_at=None; event(db,i.id,actor,'RESOLVED','Incident resolved'); audit(db,actor,'INCIDENT_RESOLVED','INCIDENT',iid); db.commit(); return i
@app.post('/api/v1/incidents/{iid}/reopen')
def reopen(iid:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Incident,iid)
    if not i: raise HTTPException(404,'Incident not found')
    i.status='OPEN'; i.resolved_at=None; i.acknowledged_at=None; event(db,i.id,actor,'REOPENED','Incident reopened'); audit(db,actor,'INCIDENT_REOPENED','INCIDENT',iid); db.commit(); return i
@app.post('/api/v1/incidents/{iid}/notes')
def note(iid:int,b:NoteCreate,actor=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Incident,iid): raise HTTPException(404,'Incident not found')
    n=IncidentNote(incident_id=iid,author_user_id=actor.id,body=b.body); db.add(n); event(db,iid,actor,'NOTE_ADDED','Incident note added'); audit(db,actor,'INCIDENT_NOTE_ADDED','INCIDENT',iid); db.commit(); return n
@app.get('/api/v1/policies')
def policies(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(EscalationPolicy).order_by(EscalationPolicy.name)).all()
@app.post('/api/v1/policies')
def policy(b:PolicyCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    p=EscalationPolicy(**b.model_dump()); db.add(p); db.flush(); audit(db,actor,'POLICY_CREATED','POLICY',p.id); db.commit(); return p
@app.get('/api/v1/policies/{pid}/levels')
def levels(pid:int, _:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(EscalationLevel).where(EscalationLevel.policy_id==pid).order_by(EscalationLevel.position)).all()
@app.post('/api/v1/policies/{pid}/levels')
def add_level(pid:int,b:LevelCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not db.get(EscalationPolicy,pid): raise HTTPException(404,'Policy not found')
    pos=(db.scalar(select(func.max(EscalationLevel.position)).where(EscalationLevel.policy_id==pid)) or 0)+1
    if b.delay_minutes<1: raise HTTPException(400,'Delay must be at least one minute')
    l=EscalationLevel(policy_id=pid,position=pos,target_type=b.target_type,target_id=b.target_id,delay_minutes=b.delay_minutes); db.add(l); audit(db,actor,'ESCALATION_LEVEL_ADDED','POLICY',pid); db.commit(); return l
@app.delete('/api/v1/policies/{pid}')
def delete_policy(pid:int,actor=Depends(admin),db:Session=Depends(get_db)):
    p=db.get(EscalationPolicy,pid)
    if not p: raise HTTPException(404,'Policy not found')
    db.delete(p); audit(db,actor,'POLICY_REMOVED','POLICY',pid); db.commit(); return {'status':'removed'}
@app.get('/api/v1/schedules')
def schedules(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(OnCallSchedule).order_by(OnCallSchedule.name)).all()
@app.post('/api/v1/schedules')
def schedule(b:ScheduleCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    if not b.member_ids: raise HTTPException(400,'At least one responder is required')
    s=OnCallSchedule(name=b.name,timezone=b.timezone,rotation_type=b.rotation_type,handoff_weekday=b.handoff_weekday,handoff_hour=b.handoff_hour,active_start_hour=b.active_start_hour,active_end_hour=b.active_end_hour); db.add(s); db.flush()
    for pos,uid in enumerate(b.member_ids):
        if not db.get(User,uid): raise HTTPException(404,f'User {uid} not found')
        db.add(RotationMember(schedule_id=s.id,user_id=uid,position=pos))
    audit(db,actor,'SCHEDULE_CREATED','SCHEDULE',s.id); db.commit(); return s
@app.get('/api/v1/schedules/{sid}/members')
def schedule_members(sid:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(RotationMember,User).join(User,User.id==RotationMember.user_id).where(RotationMember.schedule_id==sid).order_by(RotationMember.position)).all(); return [{'id':u.id,'name':u.name,'email':u.email,'position':m.position} for m,u in rows]
@app.get('/api/v1/schedules/{sid}/current')
def schedule_current(sid:int, _:User=Depends(current_user),db:Session=Depends(get_db)):
    u=oncall_user(db,sid); return {'user':serialize_user(u) if u else None}
@app.get('/api/v1/schedules/{sid}/overrides')
def overrides(sid:int, _:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(Override).where(Override.schedule_id==sid).order_by(Override.starts_at)).all()
@app.post('/api/v1/schedules/{sid}/overrides')
def override(sid:int,b:OverrideCreate,actor=Depends(admin),db:Session=Depends(get_db)):
    try: st=datetime.fromisoformat(b.starts_at.replace('Z','+00:00')); en=datetime.fromisoformat(b.ends_at.replace('Z','+00:00'))
    except ValueError: raise HTTPException(400,'Invalid timestamps')
    if en<=st: raise HTTPException(400,'End must be after start')
    if not db.get(OnCallSchedule,sid) or not db.get(User,b.to_user_id): raise HTTPException(404,'Schedule or user not found')
    o=Override(schedule_id=sid,from_user_id=b.from_user_id,to_user_id=b.to_user_id,starts_at=st,ends_at=en,reason=b.reason); db.add(o); audit(db,actor,'OVERRIDE_CREATED','SCHEDULE',sid); db.commit(); return o
@app.get('/api/v1/notifications')
def notifications(actor=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(NotificationRule).where(NotificationRule.user_id==actor.id)).all()
@app.post('/api/v1/notifications')
def add_notification(b:NotificationCreate,actor=Depends(current_user),db:Session=Depends(get_db)):
    n=NotificationRule(user_id=actor.id,channel=b.channel,destination=b.destination); db.add(n); audit(db,actor,'NOTIFICATION_RULE_CREATED','USER',actor.id); db.commit(); return n
@app.delete('/api/v1/notifications/{nid}')
def del_notification(nid:int,actor=Depends(current_user),db:Session=Depends(get_db)):
    n=db.get(NotificationRule,nid)
    if not n or n.user_id!=actor.id: raise HTTPException(404,'Notification rule not found')
    db.delete(n); db.commit(); return {'status':'removed'}
@app.get('/api/v1/audit')
def audit_logs(_:User=Depends(current_user),db:Session=Depends(get_db)): return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).all()
@app.get('/api/v1/dashboard')
def dashboard(_:User=Depends(current_user),db:Session=Depends(get_db)):
    return {'open':db.scalar(select(func.count()).select_from(Incident).where(Incident.status=='OPEN')) or 0,'acknowledged':db.scalar(select(func.count()).select_from(Incident).where(Incident.status=='ACKNOWLEDGED')) or 0,'resolved':db.scalar(select(func.count()).select_from(Incident).where(Incident.status=='RESOLVED')) or 0,'services':db.scalar(select(func.count()).select_from(Service)) or 0,'teams':db.scalar(select(func.count()).select_from(Team)) or 0}
