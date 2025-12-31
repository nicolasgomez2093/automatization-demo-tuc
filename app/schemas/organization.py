from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class OrganizationBase(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: str = "#0ea5e9"
    secondary_color: str = "#64748b"
    company_name: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    plan: str = "free"
    features: Optional[Dict] = None
    max_users: int = 5
    max_projects: int = 10
    max_storage_mb: int = 100
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    company_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
    plan: Optional[str] = None
    features: Optional[Dict] = None
    max_users: Optional[int] = None
    max_projects: Optional[int] = None
    max_storage_mb: Optional[int] = None
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    id: int
    plan: str
    is_active: bool
    features: Dict
    max_users: int
    max_projects: int
    max_storage_mb: int
    contact_email: Optional[str]
    contact_phone: Optional[str]
    billing_email: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
