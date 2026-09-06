from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: str = "RESPONDER"

class TeamCreate(BaseModel):
    name: str
    description: str = ""

class MemberCreate(BaseModel):
    user_id: int
    role: str = "MEMBER"

class ServiceCreate(BaseModel):
    name: str
    description: str = ""
    owner_team_id: Optional[int] = None

class RoutingKeyCreate(BaseModel):
    name: str = "Default"

class IncidentCreate(BaseModel):
    service_id: int
    title: str
    description: str = ""
    priority: str = "P2"
    assigned_user_id: Optional[int] = None
    assigned_team_id: Optional[int] = None

class AlertCreate(BaseModel):
    routing_key: str
    title: str
    message: str = ""
    severity: str = "error"
    dedupe_key: Optional[str] = None
    source: str = "external"

class AssignIn(BaseModel):
    user_id: Optional[int] = None
    team_id: Optional[int] = None

class NoteCreate(BaseModel):
    body: str

class PolicyCreate(BaseModel):
    name: str
    description: str = ""

class LevelCreate(BaseModel):
    target_type: str
    target_id: int
    delay_minutes: int = 5

class ScheduleCreate(BaseModel):
    name: str
    timezone: str = "UTC"
    rotation_type: str = "WEEKLY"
    start_hour: int = 9
    end_hour: int = 17
    member_ids: list[int] = []

class OverrideCreate(BaseModel):
    from_user_id: int
    to_user_id: int
    starts_at: str
    ends_at: str
    reason: str = ""
