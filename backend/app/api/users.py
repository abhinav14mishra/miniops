import secrets
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User,Invitation,TeamMember
from ..schemas import UserInvite,UserOut
from ..security import hash_password
from ..dependencies import require_admin
router=APIRouter(prefix="/api/v1/users",tags=["users"])
@router.get("",response_model=list[UserOut])
def users(db:Session=Depends(get_db),u=Depends(require_admin)): return db.query(User).order_by(User.name).all()
@router.post("/invite")
def invite(p:UserInvite,db:Session=Depends(get_db),u=Depends(require_admin)):
    if db.query(User).filter(User.email==str(p.email)).first(): raise HTTPException(409,"User already exists")
    token=secrets.token_urlsafe(32); inv=Invitation(email=str(p.email),name=p.name,role=p.role,team_id=p.team_id,token=token)
    new=User(email=str(p.email),name=p.name,role=p.role,password_hash=hash_password("ChangeMe123!"))
    db.add(inv); db.add(new); db.flush()
    if p.team_id: db.add(TeamMember(team_id=p.team_id,user_id=new.id))
    db.commit(); return {"invitation_token":token,"temporary_password":"ChangeMe123!","user":new}
