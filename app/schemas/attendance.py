from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AttendanceBase(BaseModel):
    notes: Optional[str] = None


class AttendanceCheckIn(AttendanceBase):
    pass


class AttendanceCheckOut(BaseModel):
    notes: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: int
    user_id: int
    check_in: datetime
    check_out: Optional[datetime] = None
    hours_worked: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AttendanceStats(BaseModel):
    total_days: int
    total_hours: float
    average_hours_per_day: float
    current_month_days: int
    current_month_hours: float
