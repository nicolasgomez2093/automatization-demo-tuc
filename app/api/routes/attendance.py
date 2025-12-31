from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.attendance import Attendance
from app.schemas.attendance import (
    AttendanceCheckIn, AttendanceCheckOut, AttendanceResponse, AttendanceStats
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/check-in", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def check_in(
    data: AttendanceCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check in (mark entry time)."""
    # Check if user already has an active check-in
    active_attendance = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.check_out.is_(None)
    ).first()
    
    if active_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active check-in. Please check out first."
        )
    
    attendance = Attendance(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        check_in=datetime.now(),
        notes=data.notes
    )
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.post("/check-out", response_model=AttendanceResponse)
async def check_out(
    data: AttendanceCheckOut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check out (mark exit time)."""
    # Find active check-in
    attendance = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.organization_id == current_user.organization_id,
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active check-in found. Please check in first."
        )
    
    check_out_time = datetime.now()
    attendance.check_out = check_out_time
    
    # Calculate hours worked
    time_diff = check_out_time - attendance.check_in
    attendance.hours_worked = time_diff.total_seconds() / 3600
    
    if data.notes:
        attendance.notes = data.notes
    
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.get("/", response_model=List[AttendanceResponse])
async def list_attendance(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List attendance records with advanced filters."""
    # Users can only see their own attendance unless they're manager/admin
    if user_id and user_id != current_user.id:
        if current_user.role.value not in ["superadmin", "admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view other users' attendance"
            )
        query = db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.organization_id == current_user.organization_id)
    else:
        query = db.query(Attendance).filter(Attendance.user_id == current_user.id, Attendance.organization_id == current_user.organization_id)
    
    if start_date:
        query = query.filter(Attendance.check_in >= start_date)
    if end_date:
        query = query.filter(Attendance.check_in <= end_date)
    
    attendances = query.order_by(Attendance.check_in.desc()).offset(skip).limit(limit).all()
    return attendances


@router.get("/stats", response_model=AttendanceStats)
async def get_attendance_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get attendance statistics for current user."""
    # All time stats
    all_attendances = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.organization_id == current_user.organization_id,
        Attendance.check_out.isnot(None)
    ).all()
    
    total_days = len(all_attendances)
    total_hours = sum(a.hours_worked or 0 for a in all_attendances)
    avg_hours = total_hours / total_days if total_days > 0 else 0
    
    # Current month stats
    now = datetime.now()
    month_attendances = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.organization_id == current_user.organization_id,
        Attendance.check_out.isnot(None),
        extract('year', Attendance.check_in) == now.year,
        extract('month', Attendance.check_in) == now.month
    ).all()
    
    month_days = len(month_attendances)
    month_hours = sum(a.hours_worked or 0 for a in month_attendances)
    
    return AttendanceStats(
        total_days=total_days,
        total_hours=round(total_hours, 2),
        average_hours_per_day=round(avg_hours, 2),
        current_month_days=month_days,
        current_month_hours=round(month_hours, 2)
    )


@router.get("/active", response_model=AttendanceResponse | None)
async def get_active_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current active attendance (if any)."""
    attendance = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.organization_id == current_user.organization_id,
        Attendance.check_out.is_(None)
    ).first()
    
    return attendance
