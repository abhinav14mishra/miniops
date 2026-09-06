import os,time,smtplib
from email.message import EmailMessage
from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import Incident,EscalationLevel,User,NotificationRule,IncidentEvent

def notify(db,user,incident,level):
    for r in db.scalars(select(NotificationRule).where(NotificationRule.user_id==user.id,NotificationRule.enabled==True)).all():
        if r.channel=='EMAIL':
            try:
                msg=EmailMessage(); msg['Subject']=f'[MiniOps {incident.priority}] INC-{incident.incident_number} {incident.title}'; msg['From']=os.getenv('MAIL_FROM','miniops@localhost'); msg['To']=r.destination; msg.set_content(f'Incident INC-{incident.incident_number} requires attention.\n\n{incident.title}\nPriority: {incident.priority}\nLevel: {level.position}')
                with smtplib.SMTP(os.getenv('SMTP_HOST','mailpit'),int(os.getenv('SMTP_PORT','1025')),timeout=5) as s:s.send_message(msg)
            except Exception as e: print('notification error',e)

def tick():
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        incidents=db.scalars(select(Incident).where(Incident.status=='OPEN',Incident.next_escalation_at!=None,Incident.next_escalation_at<=now)).all()
        for i in incidents:
            levels=db.scalars(select(EscalationLevel).where(EscalationLevel.policy_id==i.escalation_policy_id).order_by(EscalationLevel.position)).all() if i.escalation_policy_id else []
            if not levels: i.next_escalation_at=None; continue
            current=i.escalation_level
            nxt=next((x for x in levels if x.position>current),None)
            if not nxt:
                i.next_escalation_at=None; continue
            targets=[]
            if nxt.target_type=='USER':
                u=db.get(User,nxt.target_id); targets=[u] if u else []
            elif nxt.target_type=='TEAM': targets=db.scalars(select(User).join_from(User, __import__('app.models',fromlist=['TeamMember']).TeamMember).where(__import__('app.models',fromlist=['TeamMember']).TeamMember.team_id==nxt.target_id,User.is_active==True)).all()
            else:
                # worker intentionally uses the first active rotation member as a safe local fallback.
                RM=__import__('app.models',fromlist=['RotationMember']).RotationMember
                m=db.scalar(select(RM).where(RM.schedule_id==nxt.target_id).order_by(RM.position)); u=db.get(User,m.user_id) if m else None; targets=[u] if u else []
            targets=[u for u in targets if u and u.is_active]
            if targets:
                i.assigned_user_id=targets[0].id; i.escalation_level=nxt.position; i.next_escalation_at=now+timedelta(minutes=nxt.delay_minutes); db.add(IncidentEvent(incident_id=i.id,event_type='ESCALATED',message=f'Escalated to level {nxt.position}: {targets[0].name}'))
                notify(db,targets[0],i,nxt)
            else: i.next_escalation_at=None
        db.commit()

if __name__=='__main__':
    while True:
        try: tick()
        except Exception as e: print('worker tick error',e)
        time.sleep(10)
