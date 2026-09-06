from datetime import datetime,timedelta,timezone
from jose import jwt
from passlib.context import CryptContext
from .config import settings
pwd_context=CryptContext(schemes=["bcrypt"],deprecated="auto")
def hash_password(p): return pwd_context.hash(p)
def verify_password(p,h): return pwd_context.verify(p,h)
def create_token(uid):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub":str(uid),"exp":exp},settings.secret_key,algorithm="HS256")
