#!/usr/bin/env python3
"""
Script para crear superadmin directamente en la base de datos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from app.models import user, organization
from passlib.context import CryptContext
from sqlalchemy.orm import sessionmaker

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def fix_superadmin():
    """Crear superadmin si no existe"""
    print("🔧 Verificando/Creando superadmin...")
    
    try:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Verificar si ya existe
        existing = db.query(user.User).filter(user.User.email == "admin@sistema.com").first()
        if existing:
            print("✅ Superadmin ya existe")
            print(f"📧 Email: {existing.email}")
            print(f"👤 Username: {existing.username}")
            print(f"🔐 Role: {existing.role}")
            db.close()
            return
        
        # Crear organización si no existe
        org = db.query(organization.Organization).filter(organization.Organization.slug == "demo").first()
        if not org:
            org = organization.Organization(
                name="Demo",
                slug="demo"
            )
            db.add(org)
            db.flush()
            print("✅ Organización creada")
        
        # Crear superadmin
        admin = user.User(
            email="admin@sistema.com",
            username="admin",
            full_name="Administrador del Sistema",
            hashed_password=pwd_context.hash("admin123"),
            is_active=True,
            role="superadmin",
            organization_id=org.id
        )
        db.add(admin)
        db.commit()
        
        print("✅ Superadmin creado exitosamente!")
        print("📧 Email: admin@sistema.com")
        print("👤 Username: admin")
        print("🔑 Password: admin123")
        print("🔐 Role: superadmin")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

if __name__ == "__main__":
    fix_superadmin()
