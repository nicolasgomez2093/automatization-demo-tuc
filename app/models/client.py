from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), index=True, nullable=False)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    tags = Column(JSON, default=list)  # List of tags for categorization
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_contact = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="clients")
    messages = relationship("WhatsAppMessage", back_populates="client", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    message_sid = Column(String(100), unique=True, nullable=True)  # Twilio message ID
    from_number = Column(String(50), nullable=False)
    to_number = Column(String(50), nullable=False)
    body = Column(Text, nullable=False)
    is_incoming = Column(Boolean, default=True)
    is_automated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="messages")
