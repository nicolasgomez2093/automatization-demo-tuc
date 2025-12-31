from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp integration. Supports multiple providers."""
    
    def __init__(self):
        self.provider = settings.WHATSAPP_PROVIDER
        self._client = None
    
    def _get_twilio_client(self):
        """Initialize Twilio client."""
        try:
            from twilio.rest import Client
            return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        except Exception as e:
            logger.error(f"Error initializing Twilio: {e}")
            return None
    
    async def send_message(self, to_number: str, message: str) -> Optional[str]:
        """
        Send WhatsApp message.
        
        Args:
            to_number: Recipient phone number (with country code)
            message: Message content
        
        Returns:
            Message SID if successful, None otherwise
        """
        try:
            if self.provider == "twilio":
                return await self._send_twilio(to_number, message)
            else:
                logger.warning(f"WhatsApp provider '{self.provider}' not implemented yet")
                return None
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return None
    
    async def _send_twilio(self, to_number: str, message: str) -> Optional[str]:
        """Send message using Twilio."""
        if not self._client:
            self._client = self._get_twilio_client()
        
        if not self._client:
            raise Exception("Twilio client not initialized")
        
        # Ensure numbers are in WhatsApp format
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        
        from_number = settings.TWILIO_WHATSAPP_NUMBER
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        
        message_obj = self._client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        return message_obj.sid
    
    def parse_incoming_webhook(self, data: dict) -> dict:
        """
        Parse incoming WhatsApp webhook data.
        
        Args:
            data: Webhook payload
        
        Returns:
            Parsed message data
        """
        if self.provider == "twilio":
            return {
                "from_number": data.get("From", "").replace("whatsapp:", ""),
                "to_number": data.get("To", "").replace("whatsapp:", ""),
                "body": data.get("Body", ""),
                "message_sid": data.get("MessageSid", ""),
                "profile_name": data.get("ProfileName", "")
            }
        
        return {}


# Singleton instance
whatsapp_service = WhatsAppService()
