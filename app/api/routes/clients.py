from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.models.user import User
from app.models.client import Client, WhatsAppMessage
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse, WhatsAppMessageResponse
from app.api.deps import get_current_user, get_manager_user
from app.services.whatsapp_service import whatsapp_service
from app.services.ai_service import ai_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Create a new client."""
    # Check if client with phone already exists
    existing = db.query(Client).filter(Client.phone == client_data.phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this phone number already exists"
        )
    
    client = Client(
        organization_id=current_user.organization_id,
        name=client_data.name,
        phone=client_data.phone,
        email=client_data.email,
        company=client_data.company,
        tags=client_data.tags,
        notes=client_data.notes
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return client


@router.get("/", response_model=List[ClientResponse])
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List clients."""
    query = db.query(Client)
    
    if is_active is not None:
        query = query.filter(Client.is_active == is_active)
    
    clients = query.order_by(Client.created_at.desc()).offset(skip).limit(limit).all()
    return clients


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get client by ID."""
    client = db.query(Client).filter(Client.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Update client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    db.commit()
    db.refresh(client)
    
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Delete client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    db.delete(client)
    db.commit()
    
    return None


# WhatsApp endpoints
@router.get("/{client_id}/messages", response_model=List[WhatsAppMessageResponse])
async def get_client_messages(
    client_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WhatsApp messages for a client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    messages = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.client_id == client_id
    ).order_by(WhatsAppMessage.created_at.desc()).offset(skip).limit(limit).all()
    
    return messages


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for receiving WhatsApp messages.
    This endpoint receives incoming messages from Twilio/WhatsApp.
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"Received WhatsApp webhook: {data}")
        
        # Parse message data
        parsed = whatsapp_service.parse_incoming_webhook(data)
        
        if not parsed.get("body"):
            return {"status": "ok", "message": "Empty message"}
        
        from_number = parsed["from_number"]
        message_body = parsed["body"]
        profile_name = parsed.get("profile_name", "Unknown")
        
        # Find or create client
        client = db.query(Client).filter(Client.phone == from_number).first()
        
        if not client:
            # Auto-create client from incoming message
            # For now, use the first available organization
            # In production, this should be configured per WhatsApp number
            from app.models.organization import Organization
            default_org = db.query(Organization).first()
            
            if not default_org:
                logger.error("No organization found for WhatsApp webhook")
                return {"status": "error", "message": "No organization configured"}
            
            client = Client(
                organization_id=default_org.id,
                name=profile_name,
                phone=from_number,
                last_contact=datetime.utcnow()
            )
            db.add(client)
            db.commit()
            db.refresh(client)
            logger.info(f"Created new client: {client.name} ({client.phone})")
        else:
            # Update last contact
            client.last_contact = datetime.utcnow()
            db.commit()
        
        # Save incoming message
        incoming_msg = WhatsAppMessage(
            client_id=client.id,
            message_sid=parsed.get("message_sid"),
            from_number=from_number,
            to_number=parsed["to_number"],
            body=message_body,
            is_incoming=True,
            is_automated=False
        )
        db.add(incoming_msg)
        db.commit()
        
        # Generate AI response
        context = f"Cliente: {client.name}, Empresa: {client.company or 'N/A'}"
        ai_response = await ai_service.generate_response(
            message=message_body,
            context=context
        )
        
        # Send automated response
        message_sid = await whatsapp_service.send_message(from_number, ai_response)
        
        # Save outgoing message
        outgoing_msg = WhatsAppMessage(
            client_id=client.id,
            message_sid=message_sid,
            from_number=parsed["to_number"],
            to_number=from_number,
            body=ai_response,
            is_incoming=False,
            is_automated=True
        )
        db.add(outgoing_msg)
        db.commit()
        
        logger.info(f"Sent automated response to {client.name}")
        
        return {"status": "ok", "message": "Message processed"}
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/{client_id}/send-message")
async def send_message_to_client(
    client_id: int,
    message: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Send a manual WhatsApp message to a client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Send message
    message_sid = await whatsapp_service.send_message(client.phone, message)
    
    if not message_sid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )
    
    # Save message
    whatsapp_msg = WhatsAppMessage(
        client_id=client.id,
        message_sid=message_sid,
        from_number="",  # Your business number
        to_number=client.phone,
        body=message,
        is_incoming=False,
        is_automated=False
    )
    db.add(whatsapp_msg)
    
    # Update last contact
    client.last_contact = datetime.utcnow()
    
    db.commit()
    
    return {"status": "sent", "message_sid": message_sid}
