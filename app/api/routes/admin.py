from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.api.deps import get_current_user, get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, PlanType
from app.models.project import Project
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Solo superadmins pueden acceder a esta ruta
def require_superadmin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user

class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    company_name: Optional[str]
    plan: str
    is_active: bool
    max_users: int
    max_projects: int
    user_count: int
    project_count: int
    created_at: str
    features: dict

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    organization_id: int
    organization_name: str
    created_at: str

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = None
    max_projects: Optional[int] = None
    features: Optional[dict] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/organizations", response_model=List[OrganizationResponse])
async def get_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Get all organizations with user and project counts"""
    query = db.query(
        Organization,
        func.count(User.id).label('user_count'),
        func.count(func.distinct(Project.id)).label('project_count')
    ).outerjoin(User).outerjoin(Project).group_by(Organization.id)
    
    if search:
        query = query.filter(
            Organization.name.ilike(f"%{search}%") |
            Organization.company_name.ilike(f"%{search}%") |
            Organization.slug.ilike(f"%{search}%")
        )
    
    if active_only:
        query = query.filter(Organization.is_active == True)
    
    organizations = query.offset(skip).limit(limit).all()
    
    result = []
    for org, user_count, project_count in organizations:
        result.append(OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            company_name=org.company_name,
            plan=org.plan,
            is_active=org.is_active,
            max_users=org.max_users,
            max_projects=org.max_projects,
            user_count=user_count or 0,
            project_count=project_count or 0,
            created_at=org.created_at.isoformat(),
            features=org.features or {}
        ))
    
    return result

@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Get organization details"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    project_count = db.query(Project).filter(Project.organization_id == org_id).count()
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        company_name=org.company_name,
        plan=org.plan,
        is_active=org.is_active,
        max_users=org.max_users,
        max_projects=org.max_projects,
        user_count=user_count,
        project_count=project_count,
        created_at=org.created_at.isoformat(),
        features=org.features or {}
    )

@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: int,
    update_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Update organization"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(org, field, value)
    
    db.commit()
    db.refresh(org)
    
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    project_count = db.query(Project).filter(Project.organization_id == org_id).count()
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        company_name=org.company_name,
        plan=org.plan,
        is_active=org.is_active,
        max_users=org.max_users,
        max_projects=org.max_projects,
        user_count=user_count,
        project_count=project_count,
        created_at=org.created_at.isoformat(),
        features=org.features or {}
    )

@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Delete organization (cascades to users, projects, etc.)"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    db.delete(org)
    db.commit()
    
    return {"message": "Organization deleted successfully"}

@router.get("/users", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    active_only: bool = Query(False),
    organization_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Get all users with organization details"""
    query = db.query(User, Organization).join(Organization)
    
    if search:
        query = query.filter(
            User.email.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%") |
            User.full_name.ilike(f"%{search}%")
        )
    
    if role:
        query = query.filter(User.role == role)
    
    if active_only:
        query = query.filter(User.is_active == True)
    
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    
    users = query.offset(skip).limit(limit).all()
    
    result = []
    for user, org in users:
        result.append(UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            organization_id=user.organization_id,
            organization_name=org.name,
            created_at=user.created_at.isoformat()
        ))
    
    return result

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Update user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        organization_id=user.organization_id,
        organization_name=org.name,
        created_at=user.created_at.isoformat()
    )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Delete user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.get("/stats")
async def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Get system-wide statistics"""
    total_orgs = db.query(Organization).count()
    active_orgs = db.query(Organization).filter(Organization.is_active == True).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Users by role
    users_by_role = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    
    # Organizations by plan
    orgs_by_plan = db.query(Organization.plan, func.count(Organization.id)).group_by(Organization.plan).all()
    
    return {
        "organizations": {
            "total": total_orgs,
            "active": active_orgs,
            "by_plan": {plan: count for plan, count in orgs_by_plan}
        },
        "users": {
            "total": total_users,
            "active": active_users,
            "by_role": {role: count for role, count in users_by_role}
        }
    }
