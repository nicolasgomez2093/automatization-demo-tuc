#!/usr/bin/env python3
"""
Script para crear un usuario superadmin por defecto
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import engine, Base
from app.models.user import User, UserRole
from app.models.organization import Organization, PlanType
from app.core.security import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_superadmin():
    """Crear usuario superadmin y organización por defecto"""
    
    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    with Session(engine) as db:
        try:
            # Verificar si ya existe un superadmin
            existing_superadmin = db.query(User).filter(User.role == UserRole.SUPERADMIN.value).first()
            if existing_superadmin:
                logger.info(f"✅ Superadmin ya existe: {existing_superadmin.email}")
                return
            
            # Crear organización por defecto
            default_org = Organization(
                name="Sistema Principal",
                slug="sistema-principal",
                company_name="Plataforma de Gestión",
                plan=PlanType.ENTERPRISE.value,
                is_active=True,
                max_users=100,
                max_projects=1000,
                max_storage_mb=10000,
                features={
                    "attendance": True,
                    "expenses": True,
                    "projects": True,
                    "clients": True,
                    "whatsapp": True,
                    "ai_responses": True,
                    "file_upload": True,
                    "analytics": True,
                    "admin_panel": True
                },
                contact_email="admin@sistema.com"
            )
            
            db.add(default_org)
            db.flush()  # Para obtener el ID
            
            # Crear usuario superadmin
            superadmin = User(
                email="admin@sistema.com",
                username="admin",
                hashed_password=get_password_hash("admin123"),
                full_name="Administrador del Sistema",
                role=UserRole.SUPERADMIN.value,
                is_active=True,
                organization_id=default_org.id
            )
            
            db.add(superadmin)
            db.commit()
            
            logger.info("✅ Usuario superadmin creado exitosamente:")
            logger.info(f"   Email: admin@sistema.com")
            logger.info(f"   Usuario: admin")
            logger.info(f"   Contraseña: admin123")
            logger.info(f"   Organización: {default_org.name}")
            logger.info("")
            logger.info("⚠️  IMPORTANTE: Cambia la contraseña por defecto después del primer login!")
            
        except Exception as e:
            logger.error(f"❌ Error creando superadmin: {e}")
            db.rollback()
            raise

if __name__ == "__main__":
    create_superadmin()
