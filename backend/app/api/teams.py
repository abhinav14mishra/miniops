from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Team,TeamMember,User
from ..schemas import TeamCreate,TeamMemberAdd
from ..dependencies import get_current_user,require_admin
router=APIRouter(prefix="/api/v1/teams",tags=["teams"])
@router.get("")
def teams(db:Session=Depends(get_db),u=Depends(get_current_user)): return db.query(Team).order_by(Team.name).all()
@router.post("")
def create(p:TeamCreate,db:Session=Depends(get_db),u=Depends(require_admin)):
    t=Team(**p.model_dump());db.add(t);db.commit();db.refresh(t);return t
@router.get("/{tid}/members")
def members(tid:int,db:Session=Depends(get_db),u=Depends(get_current_user)):
    rows=db.query(TeamMember,User).join(User,User.id==TeamMember.user_id).filter(TeamMember.team_id==tid).all()
    return [{"id":x.id,"email":y.email,"name":y.name,"role":x.role} for x,y in rows]
@router.post("/{tid}/members")
def add(tid:int,p:TeamMemberAdd,db:Session=Depends(get_db),u=Depends(require_admin)):
    if not db.get(Team,tid) or not db.get(User,p.user_id): raise HTTPException(404,"Team or user not found")
    db.add(TeamMember(team_id=tid,user_id=p.user_id,role=p.role));db.commit();return {"status":"added"}
