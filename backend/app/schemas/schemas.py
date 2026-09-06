from pydantic import BaseModel, EmailStr, Field

class Login(BaseModel):
    email: EmailStr
    password: str

class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""

class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    team_id: int | None = None

class InviteCreate(BaseModel):
    email: EmailStr
    name: str
    role: str = "USER"

class MemberCreate(BaseModel):
    user_id: int
    role: str = "MEMBER"

class IntegrationCreate(BaseModel):
    name: str = "Default"

class AlertCreate(BaseModel):
    severity: str = "warning"
    title: str
    message: str = ""
    source: str = "api"
    dedupe_key: str

class AssignRequest(BaseModel):
    user_id: int | None = None
    team_id: int | None = None

class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
