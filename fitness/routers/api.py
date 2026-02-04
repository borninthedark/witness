from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from fitness.database import get_db
from fitness.models.certification import Certification
from fitness.schemas.certification import CertificationOut
from fitness.security import limiter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/certifications", response_model=list[CertificationOut])
@limiter.limit("60/minute")
def list_certs(request: Request, db: Session = Depends(get_db)):
    return db.query(Certification).all()
