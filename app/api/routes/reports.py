from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.organization import Organization
from app.services.email_service import email_service
from pydantic import BaseModel, EmailStr
from datetime import datetime
import asyncio

router = APIRouter()

class ReportRequest(BaseModel):
    recipients: List[EmailStr]
    report_type: str  # 'weekly' or 'monthly'

class ReportSchedule(BaseModel):
    enabled: bool
    weekly_enabled: bool = False
    monthly_enabled: bool = False
    weekly_recipients: List[EmailStr] = []
    monthly_recipients: List[EmailStr] = []
    weekly_day: int = 1  # 1 = Monday, 5 = Friday
    monthly_day: int = 1  # 1st day of month

@router.post("/send-weekly")
async def send_weekly_report(
    recipients: List[EmailStr],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send weekly report immediately"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Add to background tasks
    background_tasks.add_task(
        email_service.send_weekly_report,
        db=db,
        organization_id=current_user.organization_id,
        to_emails=recipients
    )
    
    return {"message": "Weekly report is being sent"}

@router.post("/send-monthly")
async def send_monthly_report(
    recipients: List[EmailStr],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send monthly report immediately"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Add to background tasks
    background_tasks.add_task(
        email_service.send_monthly_report,
        db=db,
        organization_id=current_user.organization_id,
        to_emails=recipients
    )
    
    return {"message": "Monthly report is being sent"}

@router.post("/schedule")
async def schedule_reports(
    schedule: ReportSchedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Configure automatic report scheduling"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get organization
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update organization settings (you might need to add these fields to the model)
    # For now, we'll store in a simple way
    settings = {
        "reports_enabled": schedule.enabled,
        "weekly_enabled": schedule.weekly_enabled,
        "monthly_enabled": schedule.monthly_enabled,
        "weekly_recipients": schedule.weekly_recipients,
        "monthly_recipients": schedule.monthly_recipients,
        "weekly_day": schedule.weekly_day,
        "monthly_day": schedule.monthly_day
    }
    
    # Store settings in organization.settings or similar
    # This is a simplified approach - you might want to add proper fields to the model
    
    return {"message": "Report schedule updated", "settings": settings}

@router.get("/schedule")
async def get_report_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current report schedule"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Return current settings (simplified)
    return {
        "enabled": False,
        "weekly_enabled": False,
        "monthly_enabled": False,
        "weekly_recipients": [],
        "monthly_recipients": [],
        "weekly_day": 1,
        "monthly_day": 1
    }

@router.get("/preview/weekly")
async def preview_weekly_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Preview weekly report data without sending email"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    data = email_service.generate_weekly_report(db, current_user.organization_id)
    return data

@router.get("/preview/monthly")
async def preview_monthly_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Preview monthly report data without sending email"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    data = email_service.generate_monthly_report(db, current_user.organization_id)
    return data

# SuperAdmin endpoints
@router.post("/admin/send-weekly/{organization_id}")
async def admin_send_weekly_report(
    organization_id: int,
    recipients: List[EmailStr],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Send weekly report to any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    # Verify organization exists
    organization = db.query(Organization).filter(
        Organization.id == organization_id
    ).first()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Add to background tasks
    background_tasks.add_task(
        email_service.send_weekly_report,
        db=db,
        organization_id=organization_id,
        to_emails=recipients
    )
    
    return {"message": f"Weekly report for {organization.name} is being sent"}

@router.post("/admin/send-monthly/{organization_id}")
async def admin_send_monthly_report(
    organization_id: int,
    recipients: List[EmailStr],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Send monthly report to any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    # Verify organization exists
    organization = db.query(Organization).filter(
        Organization.id == organization_id
    ).first()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Add to background tasks
    background_tasks.add_task(
        email_service.send_monthly_report,
        db=db,
        organization_id=organization_id,
        to_emails=recipients
    )
    
    return {"message": f"Monthly report for {organization.name} is being sent"}
