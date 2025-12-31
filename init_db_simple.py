#!/usr/bin/env python3
"""
Script ultra-simple para inicializar base de datos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from app.models import user, organization
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    print("🚀 Inicializando base de datos simple...")
    
    try:
        # Crear tablas
        print("🔧 Creando tablas...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas")
        
        # Crear superadmin simple
        print("👤 Creando superadmin...")
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Verificar si ya existe
        existing = db.query(user.User).filter(user.User.email == "admin@sistema.com").first()
        if existing:
            print("✅ Superadmin ya existe")
            db.close()
            return
        
        # Crear organización
        org = organization.Organization(
            name="Demo",
            slug="demo"
        )
        db.add(org)
        db.flush()
        
        # Crear superadmin
        admin = user.User(
            email="admin@sistema.com",
            username="admin",
            full_name="Admin",
            hashed_password=pwd_context.hash("admin123"),
            is_active=True,
            role="superadmin",
            organization_id=org.id
        )
        db.add(admin)
        db.commit()
        
        print("✅ Superadmin creado: admin@sistema.com / admin123")
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
