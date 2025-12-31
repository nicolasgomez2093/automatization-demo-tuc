from sqlalchemy import Column, Integer, String, Boolean, JSON, Enum, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class PlanType(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)  # cliente-1, cliente-2
    
    # White Label Configuration
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(20), default="#0ea5e9")
    secondary_color = Column(String(20), default="#64748b")
    company_name = Column(String(255), nullable=True)  # Nombre personalizado
    
    # Features habilitadas por organización
    features = Column(JSON, default={
        "attendance": True,
        "expenses": True,
        "projects": True,
        "clients": True,
        "whatsapp": False,
        "ai_responses": False,
        "file_upload": True,
        "analytics": False
    })
    
    # Límites por plan
    max_users = Column(Integer, default=5)
    max_projects = Column(Integer, default=10)
    max_storage_mb = Column(Integer, default=100)  # MB de archivos
    
    # Billing & Plan
    plan = Column(String(20), default=PlanType.FREE.value, nullable=False)
    is_active = Column(Boolean, default=True)
    trial_ends_at = Column(DateTime, nullable=True)
    
    # Contact & Billing
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    billing_email = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization {self.name} ({self.slug})>"
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if organization has a specific feature enabled."""
        return self.features.get(feature_name, False)
    
    def can_add_user(self, current_count: int) -> bool:
        """Check if organization can add more users."""
        return current_count < self.max_users
    
    def can_add_project(self, current_count: int) -> bool:
        """Check if organization can add more projects."""
        return current_count < self.max_projects
