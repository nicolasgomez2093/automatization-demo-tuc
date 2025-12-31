from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.organization import Organization
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
from pydantic import BaseModel

router = APIRouter()

class SuperadminCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: str

@router.post("/init-superadmin")
def create_superadmin(
    user_data: SuperadminCreate,
    db: Session = Depends(get_db)
):
    """Crear superadmin inicial (solo si no existe)"""
    
    # Verificar si ya existe
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        return {"message": "Superadmin already exists", "email": existing.email}
    
    # Crear organización por defecto
    org = Organization(
        name="Sistema Principal",
        slug="sistema-principal"
    )
    db.add(org)
    db.flush()
    
    # Crear superadmin
    superadmin = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        role="superadmin",
        organization_id=org.id
    )
    db.add(superadmin)
    db.commit()
    
    return {
        "message": "Superadmin created successfully",
        "email": superadmin.email,
        "username": superadmin.username,
        "role": superadmin.role
    }
