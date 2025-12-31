from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Union
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


class ClientBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    last_contact: Optional[Union[datetime, date, str]] = None

    @field_validator('last_contact', mode='before')
    @classmethod
    def parse_last_contact(cls, v):
        return parse_datetime(v)


class ClientResponse(ClientBase):
    id: int
    is_active: bool
    last_contact: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WhatsAppMessageBase(BaseModel):
    body: str
    from_number: str
    to_number: str


class WhatsAppMessageCreate(WhatsAppMessageBase):
    client_id: int
    is_incoming: bool = True
    is_automated: bool = False


class WhatsAppMessageResponse(WhatsAppMessageBase):
    id: int
    client_id: int
    message_sid: Optional[str] = None
    is_incoming: bool
    is_automated: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
