from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from jose import jwt,JWTError
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User
bearer=HTTPBearer()
def get_current_user(c:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    try: uid=int(jwt.decode(c.credentials,settings.secret_key,algorithms=["HS256"])["sub"])
    except (JWTError,KeyError,ValueError): raise HTTPException(401,"Invalid token")
    u=db.get(User,uid)
    if not u or not u.is_active: raise HTTPException(401,"Inactive user")
    return u
def require_admin(u=Depends(get_current_user)):
    if u.role!="global_admin": raise HTTPException(403,"Global admin required")
    return u
