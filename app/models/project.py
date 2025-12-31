from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, Table, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    PLANNING = "planificacion"
    IN_PROGRESS = "en_progreso"
    ON_HOLD = "pausado"
    COMPLETED = "completado"
    CANCELLED = "cancelado"


# Many-to-Many relationship table
project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime, default=datetime.utcnow)
)


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    status = Column(String(50), default=ProjectStatus.PLANNING.value, nullable=False)
    budget = Column(Float, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    # Files and images
    images = Column(JSON, default=list)  # List of image URLs
    documents = Column(JSON, default=list)  # List of document URLs
    blueprints = Column(JSON, default=list)  # List of blueprint/plan URLs
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="projects")
    client = relationship("Client", back_populates="projects")
    expenses = relationship("Expense", back_populates="project", cascade="all, delete-orphan")
    progress_updates = relationship("ProjectProgress", back_populates="project", cascade="all, delete-orphan")
    members = relationship("User", secondary=project_members, back_populates="assigned_projects")


class ProjectProgress(Base):
    __tablename__ = "project_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    description = Column(Text, nullable=False)
    progress_percentage = Column(Float, nullable=False)
    
    # Files and images for this progress update
    images = Column(JSON, default=list)  # List of image URLs
    documents = Column(JSON, default=list)  # List of document URLs
    
    # Metadata
    notes = Column(Text, nullable=True)
    hours_worked = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="progress_updates")
