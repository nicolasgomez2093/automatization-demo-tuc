#!/usr/bin/env python3
"""
Script para inicializar la base de datos en producción
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from app.models import user, organization, attendance, expense, project, client, file, notification, budget, security, document, ai_assistant, admin
from app.core.config import settings
from app.services.auth_service import get_password_hash
from sqlalchemy.orm import Session

def create_database():
    """Crear todas las tablas en la base de datos"""
    print("🔧 Creando tablas en la base de datos...")
    
    try:
        # Crear todas las tablas
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas exitosamente")
        
        # Crear superadmin si no existe
        create_superadmin()
        
        print("🎉 Base de datos inicializada correctamente!")
        
    except Exception as e:
        print(f"❌ Error al crear la base de datos: {e}")
        sys.exit(1)

def create_superadmin():
    """Crear usuario superadmin"""
    print("👤 Creando usuario superadmin...")
    
    try:
        # Crear sesión
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Verificar si ya existe el superadmin
        from app.models.user import User
        existing_admin = db.query(User).filter(User.email == "admin@sistema.com").first()
        
        if existing_admin:
            print("✅ El superadmin ya existe")
            db.close()
            return
        
        # Crear organización por defecto
        from app.models.organization import Organization
        default_org = Organization(
            name="Sistema Principal",
            description="Organización principal del sistema",
            is_active=True
        )
        db.add(default_org)
        db.flush()  # Obtener el ID
        
        # Crear superadmin
        superadmin = User(
            email="admin@sistema.com",
            username="admin",
            full_name="Administrador del Sistema",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            organization_id=default_org.id
        )
        db.add(superadmin)
        
        # Commit de los cambios
        db.commit()
        print("✅ Superadmin creado exitosamente")
        print("📧 Email: admin@sistema.com")
        print("👤 Usuario: admin")
        print("🔑 Contraseña: admin123")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error al crear superadmin: {e}")
        db.rollback()
        db.close()
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Inicializando base de datos...")
    print(f"📍 Database URL: {settings.DATABASE_URL}")
    
    create_database()
    
    print("✨ Proceso completado!")
    print("🎯 El backend está listo para funcionar!")
