from datetime import datetime
from typing import Optional,List
from pydantic import BaseModel,EmailStr,Field
class LoginRequest(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    id:int; email:str; name:str; role:str; is_active:bool
    model_config={"from_attributes":True}
class LoginOut(BaseModel): access_token:str; token_type:str="bearer"; user:UserOut
class UserInvite(BaseModel): email:EmailStr; name:str; role:str="engineer"; team_id:Optional[int]=None
class TeamCreate(BaseModel): name:str; description:str=""
class TeamMemberAdd(BaseModel): user_id:int; role:str="member"
class ServiceCreate(BaseModel): name:str; description:str=""; owner_email:str=""
class AlertCreate(BaseModel):
    service:str; severity:str="warning"; title:str; message:str; source:str="api"; dedupe_key:Optional[str]=None
class Assignment(BaseModel): user_id:Optional[int]=None; team_id:Optional[int]=None
class EventOut(BaseModel):
    id:int; event_type:str; message:str; created_at:datetime
    model_config={"from_attributes":True}
class IncidentOut(BaseModel):
    id:int; incident_number:str; service_id:int; severity:str; status:str; title:str; description:str
    assigned_to_user:Optional[int]; assigned_to_team:Optional[int]; created_at:datetime
    acknowledged_at:Optional[datetime]; resolved_at:Optional[datetime]; events:List[EventOut]=Field(default_factory=list)
