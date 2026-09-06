from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import Base,engine,SessionLocal
from .models import User,Team
from .security import hash_password
from .config import settings
from .api import auth,users,teams,services,alerts,incidents
app=FastAPI(title="MiniOps API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine);db:Session=SessionLocal()
    try:
        if not db.query(User).filter(User.email=="admin@miniops.example.com").first(): db.add(User(email="admin@miniops.example.com",name="Global Admin",role="global_admin",password_hash=hash_password("admin123")))
        if not db.query(User).filter(User.email=="engineer@miniops.example.com").first(): db.add(User(email="engineer@miniops.example.com",name="On-call Engineer",role="engineer",password_hash=hash_password("engineer123")))
        if not db.query(Team).filter(Team.name=="Platform Engineering").first(): db.add(Team(name="Platform Engineering",description="Core platform and on-call team"))
        db.commit()
    finally: db.close()
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/ready")
def ready(): return {"status":"ready"}
app.include_router(auth.router);app.include_router(users.router);app.include_router(teams.router);app.include_router(services.router);app.include_router(alerts.router);app.include_router(incidents.router)
