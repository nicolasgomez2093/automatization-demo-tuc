from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union
from datetime import datetime, date


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


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    client_id: Optional[int] = None
    status: str = "planificacion"
    budget: Optional[float] = None
    start_date: Optional[Union[datetime, date, str]] = None
    end_date: Optional[Union[datetime, date, str]] = None

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_project_dates(cls, v):
        return parse_datetime(v)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    budget: Optional[float] = None
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    start_date: Optional[Union[datetime, date, str]] = None
    end_date: Optional[Union[datetime, date, str]] = None
    images: Optional[List[str]] = None
    documents: Optional[List[str]] = None
    blueprints: Optional[List[str]] = None

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_project_dates(cls, v):
        return parse_datetime(v)


class ProjectResponse(ProjectBase):
    id: int
    progress_percentage: float
    created_at: datetime
    updated_at: datetime
    images: Optional[List[str]] = None
    documents: Optional[List[str]] = None
    blueprints: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class ProjectProgressBase(BaseModel):
    description: str
    progress_percentage: float = Field(..., ge=0, le=100)
    images: Optional[List[str]] = None
    documents: Optional[List[str]] = None
    notes: Optional[str] = None
    hours_worked: Optional[float] = None


class ProjectProgressCreate(ProjectProgressBase):
    pass  # project_id comes from URL path parameter


class ProjectProgressResponse(ProjectProgressBase):
    id: int
    project_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
