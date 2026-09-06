from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
class LoginIn(BaseModel): email:EmailStr; password:str
class UserCreate(BaseModel): email:EmailStr; name:str=Field(min_length=1,max_length=120); role:str='RESPONDER'; password:Optional[str]=None
class InvitationCreate(BaseModel): email:EmailStr; name:str; role:str='RESPONDER'
class TeamCreate(BaseModel): name:str; description:str=''
class MemberCreate(BaseModel): user_id:int; role:str='MEMBER'
class ServiceCreate(BaseModel): name:str; description:str=''; owner_team_id:Optional[int]=None; escalation_policy_id:Optional[int]=None
class RoutingKeyCreate(BaseModel): name:str
class IncidentCreate(BaseModel): service_id:int; title:str; description:str=''; priority:Literal['P1','P2','P3','P4']='P2'; assigned_user_id:Optional[int]=None; assigned_team_id:Optional[int]=None
class AssignIn(BaseModel): user_id:Optional[int]=None; team_id:Optional[int]=None
class AlertCreate(BaseModel): routing_key:str; title:str; message:str=''; severity:str='warning'; source:str='integration'; dedupe_key:Optional[str]=None; payload:dict={}
class NoteCreate(BaseModel): body:str=Field(min_length=1)
class PolicyCreate(BaseModel): name:str; description:str=''; repeat_count:int=0
class LevelCreate(BaseModel): target_type:Literal['USER','SCHEDULE','TEAM']; target_id:int; delay_minutes:int=5
class ScheduleCreate(BaseModel): name:str; timezone:str='UTC'; rotation_type:Literal['DAILY','WEEKLY','MONTHLY']='WEEKLY'; handoff_weekday:int=0; handoff_hour:int=9; active_start_hour:int=0; active_end_hour:int=24; member_ids:list[int]=[]
class OverrideCreate(BaseModel): from_user_id:int; to_user_id:int; starts_at:str; ends_at:str; reason:str=''
class NotificationCreate(BaseModel): channel:Literal['EMAIL','WEBHOOK','IN_APP']; destination:str
