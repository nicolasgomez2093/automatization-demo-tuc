from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class TwoFactorMethod(enum.Enum):
    TOTP = "totp"  # Time-based One-Time Password
    SMS = "sms"    # SMS verification
    EMAIL = "email" # Email verification
    BACKUP_CODE = "backup_code" # Backup codes

class AuditAction(enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    SETTINGS_CHANGE = "settings_change"
    PERMISSION_CHANGE = "permission_change"

class UserTwoFactor(Base):
    __tablename__ = "user_two_factor"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 2FA Configuration
    is_enabled = Column(Boolean, default=False)
    method = Column(Enum(TwoFactorMethod), nullable=True)
    secret = Column(String(255), nullable=True)  # TOTP secret
    phone_number = Column(String(20), nullable=True)  # For SMS
    backup_codes = Column(JSON, nullable=True)  # List of backup codes
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="two_factor")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Action Details
    action = Column(Enum(AuditAction), nullable=False)
    resource_type = Column(String(100), nullable=False)  # 'user', 'project', 'expense', etc.
    resource_id = Column(String(100), nullable=True)
    
    # Request Details
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    
    # Data Changes
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User", back_populates="audit_logs")

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Attempt Details
    email = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    
    # Result
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(255), nullable=True)  # 'invalid_password', 'account_locked', '2fa_required', etc.
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

class SecurityPolicy(Base):
    __tablename__ = "security_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Password Policy
    password_min_length = Column(Integer, default=8)
    password_require_uppercase = Column(Boolean, default=True)
    password_require_lowercase = Column(Boolean, default=True)
    password_require_numbers = Column(Boolean, default=True)
    password_require_symbols = Column(Boolean, default=True)
    password_history_count = Column(Integer, default=5)  # Number of previous passwords to remember
    password_expiry_days = Column(Integer, default=90)  # Password expiry in days
    
    # Session Policy
    session_timeout_minutes = Column(Integer, default=480)  # 8 hours
    max_concurrent_sessions = Column(Integer, default=3)
    
    # 2FA Policy
    require_2fa = Column(Boolean, default=False)
    require_2fa_for_admins = Column(Boolean, default=True)
    allowed_2fa_methods = Column(JSON, default=lambda: ["totp", "sms", "email"])
    
    # Lockout Policy
    max_login_attempts = Column(Integer, default=5)
    lockout_duration_minutes = Column(Integer, default=30)
    
    # IP Restrictions
    allowed_ip_ranges = Column(JSON, nullable=True)  # List of allowed IP ranges
    block_suspicious_ips = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    creator = relationship("User")

class PasswordHistory(Base):
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Password Hash
    password_hash = Column(String(255), nullable=False)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="password_history")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Session Details
    session_token = Column(String(255), unique=True, nullable=False)
    refresh_token = Column(String(255), unique=True, nullable=True)
    
    # Device Info
    device_id = Column(String(255), nullable=True)
    device_name = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True)  # 'desktop', 'mobile', 'tablet'
    
    # Location Info
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    location = Column(JSON, nullable=True)  # Country, city, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    is_2fa_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    organization = relationship("Organization")

class SSOProvider(Base):
    __tablename__ = "sso_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Provider Configuration
    provider_name = Column(String(50), nullable=False)  # 'google', 'microsoft', 'azure_ad'
    client_id = Column(String(255), nullable=False)
    client_secret = Column(String(255), nullable=False)
    tenant_id = Column(String(255), nullable=True)  # For Azure AD
    
    # Configuration
    redirect_uri = Column(String(500), nullable=False)
    scopes = Column(JSON, nullable=True)  # OAuth scopes
    
    # Status
    is_enabled = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    creator = relationship("User")

class UserSSO(Base):
    __tablename__ = "user_sso"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sso_provider_id = Column(Integer, ForeignKey("sso_providers.id"), nullable=False)
    
    # SSO Identity
    provider_user_id = Column(String(255), nullable=False)  # User ID in the provider system
    email = Column(String(255), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sso_accounts")
    sso_provider = relationship("SSOProvider")

# Update relationships in existing models
from app.models.user import User
from app.models.organization import Organization

# Add relationships to User
User.two_factor = relationship("UserTwoFactor", back_populates="user", uselist=False)
User.audit_logs = relationship("AuditLog", back_populates="user")
User.password_history = relationship("PasswordHistory", back_populates="user")
User.sessions = relationship("UserSession", back_populates="user")
User.sso_accounts = relationship("UserSSO", back_populates="user")

# Add relationship to Organization
Organization.audit_logs = relationship("AuditLog", back_populates="organization")
