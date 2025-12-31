from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union
from datetime import datetime, date
from app.schemas.user import UserResponse
from app.schemas.project import ProjectBase


def parse_datetime(value):
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        # Try various date formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y',
            '%d-%m-%Y',
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed
            except ValueError:
                continue
    raise ValueError('Invalid datetime format')


class ExpenseBase(BaseModel):
    amount: float = Field(..., gt=0)
    category: str
    description: str
    project_id: Optional[int] = None
    receipt_url: Optional[str] = None
    expense_date: Optional[Union[datetime, date, str]] = None

    @field_validator('expense_date', mode='before')
    @classmethod
    def parse_expense_date(cls, v):
        return parse_datetime(v)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    receipt_url: Optional[str] = None
    expense_date: Optional[Union[datetime, date, str]] = None

    @field_validator('expense_date', mode='before')
    @classmethod
    def parse_expense_date(cls, v):
        return parse_datetime(v)


class ExpenseResponse(ExpenseBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None
    project: Optional[ProjectBase] = None
    
    class Config:
        from_attributes = True


class ExpenseStats(BaseModel):
    total_expenses: float
    by_category: dict
    by_project: dict
    count: int
