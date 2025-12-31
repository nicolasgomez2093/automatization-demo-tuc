from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class BudgetStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXCEEDED = "exceeded"

class BudgetType(enum.Enum):
    PROJECT = "project"
    DEPARTMENT = "department"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Basic Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(Enum(BudgetType), nullable=False)
    status = Column(Enum(BudgetStatus), default=BudgetStatus.DRAFT)
    
    # Budget Amounts
    total_amount = Column(Float, nullable=False)
    spent_amount = Column(Float, default=0.0)
    remaining_amount = Column(Float)
    
    # Time Period
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # References
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    department_id = Column(Integer, nullable=True)  # If departments are implemented
    
    # Alert Thresholds
    warning_threshold = Column(Float, default=80.0)  # Percentage
    critical_threshold = Column(Float, default=95.0)  # Percentage
    
    # Approval Settings
    requires_approval = Column(Boolean, default=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    max_single_expense = Column(Float, nullable=True)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="budgets")
    project = relationship("Project", back_populates="budgets")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approver_id])
    
    # Calculated properties
    @property
    def utilization_percentage(self):
        if self.total_amount == 0:
            return 0
        return (self.spent_amount / self.total_amount) * 100
    
    @property
    def is_warning_threshold_exceeded(self):
        return self.utilization_percentage >= self.warning_threshold
    
    @property
    def is_critical_threshold_exceeded(self):
        return self.utilization_percentage >= self.critical_threshold
    
    @property
    def is_over_budget(self):
        return self.spent_amount > self.total_amount

class BudgetTransaction(Base):
    __tablename__ = "budget_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Transaction Details
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # 'expense', 'adjustment', 'transfer'
    description = Column(Text)
    
    # References
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    budget = relationship("Budget", back_populates="transactions")
    expense = relationship("Expense")
    creator = relationship("User")

class BudgetAlert(Base):
    __tablename__ = "budget_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Alert Details
    alert_type = Column(String(50), nullable=False)  # 'warning', 'critical', 'exceeded'
    threshold_percentage = Column(Float, nullable=False)
    current_percentage = Column(Float, nullable=False)
    
    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    budget = relationship("Budget", back_populates="alerts")
    acknowledged_user = relationship("User")

class ExpenseRequest(Base):
    __tablename__ = "expense_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Request Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100))
    
    # Budget Reference
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=True)
    
    # Requester
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Approval Workflow
    status = Column(String(50), default="pending")  # 'pending', 'approved', 'rejected', 'cancelled'
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Supporting Documents
    receipt_url = Column(String(500))
    supporting_documents = Column(Text)  # JSON array of document URLs
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    budget = relationship("Budget", back_populates="expense_requests")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])

class ROIAnalysis(Base):
    __tablename__ = "roi_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Project Reference
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Financial Metrics
    total_investment = Column(Float, nullable=False)
    total_return = Column(Float, default=0.0)
    roi_percentage = Column(Float, default=0.0)
    payback_period_months = Column(Integer, nullable=True)
    
    # Time Period
    analysis_start_date = Column(DateTime, nullable=False)
    analysis_end_date = Column(DateTime, nullable=False)
    
    # Analysis Details
    revenue_streams = Column(Text)  # JSON
    cost_breakdown = Column(Text)  # JSON
    assumptions = Column(Text)
    
    # Status
    status = Column(String(50), default="draft")  # 'draft', 'active', 'completed', 'archived'
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    project = relationship("Project", back_populates="roi_analyses")
    creator = relationship("User")

# Update relationships in other models
from app.models.project import Project
from app.models.organization import Organization

# Add relationships to existing models
Project.budgets = relationship("Budget", back_populates="project")
Project.roi_analyses = relationship("ROIAnalysis", back_populates="project")
Organization.budgets = relationship("Budget", back_populates="organization")

# Add relationships to Budget
Budget.transactions = relationship("BudgetTransaction", back_populates="budget")
Budget.alerts = relationship("BudgetAlert", back_populates="budget")
Budget.expense_requests = relationship("ExpenseRequest", back_populates="budget")
