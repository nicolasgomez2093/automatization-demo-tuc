from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.schemas.organization import OrganizationResponse, OrganizationUpdate, OrganizationCreate
from app.api.deps import get_current_user, require_role
import re
from datetime import datetime

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's organization details."""
    org = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return org


@router.put("/me", response_model=OrganizationResponse)
async def update_my_organization(
    org_data: OrganizationUpdate,
    current_user: User = Depends(require_role(["admin", "superadmin"])),
    db: Session = Depends(get_db)
):
    """Update organization settings (admin only)."""
    org = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Update fields
    for key, value in org_data.dict(exclude_unset=True).items():
        setattr(org, key, value)
    
    db.commit()
    db.refresh(org)
    
    return org


@router.get("/features")
async def get_organization_features(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get enabled features for current organization."""
    org = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return {
        "features": org.features,
        "plan": org.plan,
        "limits": {
            "max_users": org.max_users,
            "max_projects": org.max_projects,
            "max_storage_mb": org.max_storage_mb
        }
    }


@router.get("/stats")
async def get_organization_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get usage statistics for current organization."""
    from app.models.project import Project
    from app.models.expense import Expense
    from app.models.client import Client
    
    org_id = current_user.organization_id
    
    # Count resources
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    project_count = db.query(Project).filter(Project.organization_id == org_id).count()
    client_count = db.query(Client).filter(Client.organization_id == org_id).count()
    expense_count = db.query(Expense).filter(Expense.organization_id == org_id).count()
    
    # Get organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    
    return {
        "usage": {
            "users": user_count,
            "projects": project_count,
            "clients": client_count,
            "expenses": expense_count
        },
        "limits": {
            "max_users": org.max_users,
            "max_projects": org.max_projects,
            "max_storage_mb": org.max_storage_mb
        },
        "percentage": {
            "users": (user_count / org.max_users * 100) if org.max_users > 0 else 0,
            "projects": (project_count / org.max_projects * 100) if org.max_projects > 0 else 0
        }
    }


# SuperAdmin endpoints for managing all organizations
def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from organization name."""
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


@router.get("/admin/all", response_model=List[OrganizationResponse])
async def list_all_organizations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """List all organizations (SuperAdmin only)."""
    organizations = db.query(Organization).offset(skip).limit(limit).all()
    return organizations


@router.post("/admin/create", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Create new organization (SuperAdmin only)."""
    # Check if slug already exists
    slug = generate_slug(org_data.name)
    existing_slug = db.query(Organization).filter(Organization.slug == slug).first()
    if existing_slug:
        counter = 1
        while db.query(Organization).filter(Organization.slug == f"{slug}-{counter}").first():
            counter += 1
        slug = f"{slug}-{counter}"
    
    organization = Organization(
        name=org_data.name,
        slug=slug,
        company_name=org_data.company_name,
        contact_email=org_data.contact_email,
        contact_phone=org_data.contact_phone,
        billing_email=org_data.billing_email,
        plan=org_data.plan,
        max_users=org_data.max_users,
        max_projects=org_data.max_projects,
        max_storage_mb=org_data.max_storage_mb,
        primary_color=org_data.primary_color,
        secondary_color=org_data.secondary_color,
        features=org_data.features,
        is_active=org_data.is_active
    )
    
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    return organization


@router.get("/admin/{org_id}", response_model=OrganizationResponse)
async def get_organization_admin(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Get organization details (SuperAdmin only)."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return organization


@router.put("/admin/{org_id}", response_model=OrganizationResponse)
async def update_organization_admin(
    org_id: int,
    org_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Update organization (SuperAdmin only)."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Update fields
    update_data = org_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "name" and value:
            # Generate new slug if name changed
            new_slug = generate_slug(value)
            existing_slug = db.query(Organization).filter(
                Organization.slug == new_slug,
                Organization.id != org_id
            ).first()
            if existing_slug:
                counter = 1
                while db.query(Organization).filter(
                    Organization.slug == f"{new_slug}-{counter}",
                    Organization.id != org_id
                ).first():
                    counter += 1
                new_slug = f"{new_slug}-{counter}"
            organization.slug = new_slug
        setattr(organization, field, value)
    
    organization.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(organization)
    
    return organization


@router.post("/admin/{org_id}/toggle-status")
async def toggle_organization_status(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Toggle organization active status (SuperAdmin only)."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    organization.is_active = not organization.is_active
    organization.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(organization)
    
    return {
        "message": f"Organization {'activated' if organization.is_active else 'deactivated'} successfully",
        "is_active": organization.is_active
    }


@router.delete("/admin/{org_id}")
async def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Delete organization (SuperAdmin only)."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Don't allow deletion if there are active users
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete organization with {user_count} active users"
        )
    
    db.delete(organization)
    db.commit()
    
    return {"message": "Organization deleted successfully"}
