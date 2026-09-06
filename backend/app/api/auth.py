from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest,LoginOut,UserOut
from ..security import verify_password,create_token
from ..dependencies import get_current_user
router=APIRouter(prefix="/api/v1/auth",tags=["auth"])
@router.post("/login",response_model=LoginOut)
def login(p:LoginRequest,db:Session=Depends(get_db)):
    u=db.query(User).filter(User.email==str(p.email)).first()
    if not u or not verify_password(p.password,u.password_hash): raise HTTPException(401,"Invalid email or password")
    return LoginOut(access_token=create_token(u.id),user=u)
@router.get("/me",response_model=UserOut)
def me(u=Depends(get_current_user)): return u
