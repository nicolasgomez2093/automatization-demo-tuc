from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class DocumentStatus(enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    EXPIRED = "expired"

class DocumentType(enum.Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    REPORT = "report"
    PROPOSAL = "proposal"
    TIMESHEET = "timesheet"
    ID_DOCUMENT = "id_document"
    CERTIFICATE = "certificate"
    OTHER = "other"

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Basic Information
    title = Column(String(255), nullable=False)
    description = Column(Text)
    document_type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.DRAFT)
    
    # File Information
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 hash
    
    # Version Control
    version = Column(String(20), default="1.0")
    parent_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    is_latest_version = Column(Boolean, default=True)
    
    # Metadata
    tags = Column(JSON, nullable=True)  # List of tags
    document_metadata = Column(JSON, nullable=True)  # Additional metadata
    
    # Security
    is_encrypted = Column(Boolean, default=False)
    encryption_key_id = Column(String(255), nullable=True)
    
    # Access Control
    is_public = Column(Boolean, default=False)
    allowed_users = Column(JSON, nullable=True)  # List of user IDs
    allowed_roles = Column(JSON, nullable=True)  # List of roles
    
    # References
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    organization = relationship("Organization")
    project = relationship("Project", back_populates="documents")
    client = relationship("Client", back_populates="documents")
    user = relationship("User", back_populates="documents")
    
    # Self-referential relationship for versioning
    parent_document = relationship("Document", remote_side=[id])
    child_documents = relationship("Document")
    
    # Other relationships
    signatures = relationship("DocumentSignature", back_populates="document")
    approvals = relationship("DocumentApproval", back_populates="document")

class DocumentSignature(Base):
    __tablename__ = "document_signatures"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Signer Information
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signer_name = Column(String(255), nullable=False)
    signer_email = Column(String(255), nullable=False)
    
    # Signature Details
    signature_type = Column(String(50), nullable=False)  # 'digital', 'electronic', 'biometric'
    signature_data = Column(Text, nullable=False)  # Base64 encoded signature
    certificate_data = Column(Text, nullable=True)  # Digital certificate
    
    # Timestamp and Location
    signed_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    location = Column(JSON, nullable=True)  # GPS coordinates if available
    
    # Legal Information
    legal_statement = Column(Text, nullable=True)
    agreement_text = Column(Text, nullable=True)
    
    # Status
    is_valid = Column(Boolean, default=True)
    verification_hash = Column(String(64), nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="signatures")
    user = relationship("User")
    organization = relationship("Organization")

class DocumentApproval(Base):
    __tablename__ = "document_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Approval Workflow
    workflow_step = Column(Integer, nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_role = Column(String(50), nullable=False)  # 'manager', 'legal', 'finance', etc.
    
    # Decision
    status = Column(String(20), nullable=False)  # 'pending', 'approved', 'rejected'
    decision_at = Column(DateTime, nullable=True)
    comments = Column(Text, nullable=True)
    
    # Required Actions
    requires_signature = Column(Boolean, default=False)
    requires_document_review = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="approvals")
    approver = relationship("User")
    organization = relationship("Organization")

class ConsultantResource(Base):
    __tablename__ = "consultant_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Consultant Information
    consultant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Resource Allocation
    allocated_hours = Column(Float, nullable=False)
    hourly_rate = Column(Float, nullable=False)
    cost_per_hour = Column(Float, nullable=False)
    
    # Time Tracking
    actual_hours_worked = Column(Float, default=0.0)
    billable_hours = Column(Float, default=0.0)
    non_billable_hours = Column(Float, default=0.0)
    
    # Financial Metrics
    total_cost = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    profit_margin = Column(Float, default=0.0)
    
    # Performance Metrics
    utilization_rate = Column(Float, default=0.0)  # Percentage of allocated hours used
    efficiency_score = Column(Float, default=0.0)  # Performance rating
    
    # Time Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    consultant = relationship("User", foreign_keys=[consultant_id])
    project = relationship("Project", foreign_keys=[project_id])

class ProjectProfitability(Base):
    __tablename__ = "project_profitability"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Financial Metrics
    total_budget = Column(Float, nullable=False)
    total_costs = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    gross_profit = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    
    # Profitability Ratios
    gross_margin = Column(Float, default=0.0)  # Gross profit / revenue
    net_margin = Column(Float, default=0.0)    # Net profit / revenue
    roi_percentage = Column(Float, default=0.0)  # Return on investment
    
    # Cost Breakdown
    labor_costs = Column(Float, default=0.0)
    material_costs = Column(Float, default=0.0)
    overhead_costs = Column(Float, default=0.0)
    other_costs = Column(Float, default=0.0)
    
    # Time Metrics
    estimated_hours = Column(Float, nullable=False)
    actual_hours = Column(Float, default=0.0)
    hours_variance = Column(Float, default=0.0)
    
    # Performance Metrics
    schedule_performance = Column(Float, default=0.0)  # SPI
    cost_performance = Column(Float, default=0.0)     # CPI
    quality_score = Column(Float, default=0.0)
    
    # Time Period
    analysis_date = Column(DateTime, default=datetime.utcnow)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    project = relationship("Project", back_populates="profitability")

class OrganizationKPI(Base):
    __tablename__ = "organization_kpis"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # KPI Category
    category = Column(String(50), nullable=False)  # 'financial', 'operational', 'productivity', etc.
    kpi_name = Column(String(100), nullable=False)
    kpi_code = Column(String(50), nullable=False)
    
    # Values
    current_value = Column(Float, nullable=False)
    target_value = Column(Float, nullable=True)
    previous_value = Column(Float, nullable=True)
    
    # Metrics
    unit = Column(String(20), nullable=False)  # '%', '$', 'hours', 'count', etc.
    change_percentage = Column(Float, default=0.0)
    trend = Column(String(10), default='neutral')  # 'up', 'down', 'neutral'
    
    # Status
    status = Column(String(20), default='normal')  # 'critical', 'warning', 'normal', 'good'
    
    # Time Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    # Additional Data
    report_metadata = Column(JSON, nullable=True)
    
    # Relationships
    organization = relationship("Organization")

class TeamProductivity(Base):
    __tablename__ = "team_productivity"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Team/User Information
    team_id = Column(Integer, nullable=True)  # If team-based
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_name = Column(String(255), nullable=True)
    
    # Productivity Metrics
    tasks_completed = Column(Integer, default=0)
    tasks_in_progress = Column(Integer, default=0)
    tasks_overdue = Column(Integer, default=0)
    
    # Time Metrics
    hours_worked = Column(Float, default=0.0)
    hours_billable = Column(Float, default=0.0)
    hours_non_billable = Column(Float, default=0.0)
    utilization_rate = Column(Float, default=0.0)
    
    # Quality Metrics
    quality_score = Column(Float, default=0.0)
    client_satisfaction = Column(Float, default=0.0)
    rework_percentage = Column(Float, default=0.0)
    
    # Financial Metrics
    revenue_generated = Column(Float, default=0.0)
    cost_incurred = Column(Float, default=0.0)
    profit_contribution = Column(Float, default=0.0)
    
    # Performance Indicators
    efficiency_score = Column(Float, default=0.0)
    productivity_index = Column(Float, default=0.0)
    performance_rating = Column(Float, default=0.0)
    
    # Time Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User", foreign_keys=[user_id])

# Update relationships in existing models
from app.models.project import Project
from app.models.client import Client
from app.models.user import User
from app.models.organization import Organization

# Add relationships to existing models
Project.documents = relationship("Document", back_populates="project")
Project.profitability = relationship("ProjectProfitability", back_populates="project")
Client.documents = relationship("Document", back_populates="client")
User.documents = relationship("Document", back_populates="user")
