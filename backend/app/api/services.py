from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Service
from ..schemas import ServiceCreate
from ..dependencies import require_admin
router=APIRouter(prefix="/api/v1/services",tags=["services"])
@router.get("")
def list_services(db:Session=Depends(get_db),u=Depends(require_admin)): return db.query(Service).order_by(Service.name).all()
@router.post("")
def create(p:ServiceCreate,db:Session=Depends(get_db),u=Depends(require_admin)):
    s=Service(**p.model_dump());db.add(s);db.commit();db.refresh(s);return s
