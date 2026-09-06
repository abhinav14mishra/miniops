from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    email:Mapped[str]=mapped_column(String(320),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(120))
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(30),default="engineer")
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Team(Base):
    __tablename__="teams"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    description:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class TeamMember(Base):
    __tablename__="team_members"
    id:Mapped[int]=mapped_column(primary_key=True)
    team_id:Mapped[int]=mapped_column(ForeignKey("teams.id",ondelete="CASCADE"))
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"))
    role:Mapped[str]=mapped_column(String(30),default="member")
    __table_args__=(UniqueConstraint("team_id","user_id",name="uq_team_user"),)
class Invitation(Base):
    __tablename__="invitations"
    id:Mapped[int]=mapped_column(primary_key=True)
    email:Mapped[str]=mapped_column(String(320))
    name:Mapped[str]=mapped_column(String(120))
    role:Mapped[str]=mapped_column(String(30),default="engineer")
    team_id:Mapped[Optional[int]]=mapped_column(ForeignKey("teams.id",ondelete="SET NULL"),nullable=True)
    token:Mapped[str]=mapped_column(String(120),unique=True)
    accepted:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Service(Base):
    __tablename__="services"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    description:Mapped[str]=mapped_column(Text,default="")
    owner_email:Mapped[str]=mapped_column(String(320),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Alert(Base):
    __tablename__="alerts"
    id:Mapped[int]=mapped_column(primary_key=True)
    service_id:Mapped[int]=mapped_column(ForeignKey("services.id"))
    severity:Mapped[str]=mapped_column(String(20),default="warning")
    title:Mapped[str]=mapped_column(String(255))
    message:Mapped[str]=mapped_column(Text)
    source:Mapped[str]=mapped_column(String(120),default="api")
    dedupe_key:Mapped[str]=mapped_column(String(255),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Incident(Base):
    __tablename__="incidents"
    id:Mapped[int]=mapped_column(primary_key=True)
    incident_number:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    service_id:Mapped[int]=mapped_column(ForeignKey("services.id"))
    alert_id:Mapped[int]=mapped_column(ForeignKey("alerts.id"))
    severity:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(30),default="OPEN")
    title:Mapped[str]=mapped_column(String(255))
    description:Mapped[str]=mapped_column(Text,default="")
    assigned_to_user:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    assigned_to_team:Mapped[Optional[int]]=mapped_column(ForeignKey("teams.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    acknowledged_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    resolved_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
class IncidentEvent(Base):
    __tablename__="incident_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    incident_id:Mapped[int]=mapped_column(ForeignKey("incidents.id",ondelete="CASCADE"))
    actor_user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    event_type:Mapped[str]=mapped_column(String(50))
    message:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
