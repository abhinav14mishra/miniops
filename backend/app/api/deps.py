from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from app.db.session import get_db
from app.core.config import settings
from app.models.models import User

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        uid = int(jwt.decode(authorization[7:], settings.secret_key, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or unknown user")
    return user

def admin_only(user: User = Depends(current_user)):
    if user.role != "GLOBAL_ADMIN":
        raise HTTPException(status_code=403, detail="Global admin required")
    return user
