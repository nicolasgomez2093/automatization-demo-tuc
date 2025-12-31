"""
Initialize database with organizations and sample data.
Run this after creating tables with init_db.py
"""
from app.core.database import SessionLocal
from app.models.organization import Organization, PlanType
from app.models.user import User, UserRole
from app.core.security import get_password_hash


def create_default_organization():
    """Create default organization with admin user."""
    db = SessionLocal()
    
    try:
        # Check if organization already exists
        existing_org = db.query(Organization).filter(Organization.slug == "default").first()
        if existing_org:
            print("✅ Default organization already exists")
            return existing_org
        
        # Create default organization
        org = Organization(
            name="Empresa Demo",
            slug="default",
            primary_color="#0ea5e9",
            secondary_color="#64748b",
            company_name="Sistema de Gestión",
            plan=PlanType.PRO,
            max_users=50,
            max_projects=100,
            max_storage_mb=1000,
            features={
                "attendance": True,
                "expenses": True,
                "projects": True,
                "clients": True,
                "whatsapp": True,
                "ai_responses": True,
                "file_upload": True,
                "analytics": True
            },
            is_active=True,
            contact_email="admin@demo.com"
        )
        
        db.add(org)
        db.commit()
        db.refresh(org)
        
        print(f"✅ Organization created: {org.name} (ID: {org.id}, Slug: {org.slug})")
        
        # Create superadmin user
        admin = User(
            organization_id=org.id,
            email="admin@demo.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="Administrador",
            role=UserRole.SUPERADMIN,
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print(f"✅ Admin user created: {admin.username}")
        print(f"   Email: {admin.email}")
        print(f"   Password: admin123")
        print(f"   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
        
        return org
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_sample_organizations():
    """Create sample organizations for testing."""
    db = SessionLocal()
    
    organizations = [
        {
            "name": "Constructora ABC",
            "slug": "constructora-abc",
            "primary_color": "#ff6b6b",
            "plan": PlanType.PRO,
            "admin_email": "admin@constructora-abc.com",
            "admin_username": "admin_abc",
            "features": {
                "attendance": True,
                "expenses": True,
                "projects": True,
                "clients": True,
                "whatsapp": True,
                "ai_responses": True,
                "file_upload": True
            }
        },
        {
            "name": "Servicios XYZ",
            "slug": "servicios-xyz",
            "primary_color": "#4ecdc4",
            "plan": PlanType.BASIC,
            "admin_email": "admin@servicios-xyz.com",
            "admin_username": "admin_xyz",
            "features": {
                "attendance": True,
                "expenses": True,
                "projects": True,
                "clients": False,
                "whatsapp": False,
                "ai_responses": False,
                "file_upload": True
            }
        }
    ]
    
    try:
        for org_data in organizations:
            # Check if exists
            existing = db.query(Organization).filter(
                Organization.slug == org_data["slug"]
            ).first()
            
            if existing:
                print(f"⏭️  Organization {org_data['slug']} already exists")
                continue
            
            # Create organization
            org = Organization(
                name=org_data["name"],
                slug=org_data["slug"],
                primary_color=org_data["primary_color"],
                plan=org_data["plan"],
                features=org_data["features"],
                max_users=20 if org_data["plan"] == PlanType.BASIC else 50,
                max_projects=50 if org_data["plan"] == PlanType.BASIC else 100,
                max_storage_mb=500 if org_data["plan"] == PlanType.BASIC else 1000,
                is_active=True,
                contact_email=org_data["admin_email"]
            )
            
            db.add(org)
            db.commit()
            db.refresh(org)
            
            # Create admin user
            admin = User(
                organization_id=org.id,
                email=org_data["admin_email"],
                username=org_data["admin_username"],
                hashed_password=get_password_hash("demo123"),
                full_name=f"Admin {org.name}",
                role=UserRole.ADMIN,
                is_active=True
            )
            
            db.add(admin)
            db.commit()
            
            print(f"✅ Organization: {org.name}")
            print(f"   Slug: {org.slug}")
            print(f"   Admin: {admin.username} / demo123")
            print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Initializing Database with Organizations")
    print("=" * 60)
    print()
    
    print("1. Creating default organization...")
    create_default_organization()
    print()
    
    print("2. Creating sample organizations...")
    create_sample_organizations()
    print()
    
    print("=" * 60)
    print("✅ Database initialized successfully!")
    print("=" * 60)
    print()
    print("Default credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print()
    print("⚠️  Remember to change default passwords!")
