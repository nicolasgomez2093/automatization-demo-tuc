from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered responses. Supports multiple providers."""
    
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self._client = None
    
    def _get_openai_client(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            return OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Error initializing OpenAI: {e}")
            return None
    
    def _get_anthropic_client(self):
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic
            return Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception as e:
            logger.error(f"Error initializing Anthropic: {e}")
            return None
    
    async def generate_response(
        self,
        message: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate AI response based on the configured provider.
        
        Args:
            message: User message to respond to
            context: Additional context about the conversation
            system_prompt: Custom system prompt
        
        Returns:
            AI-generated response
        """
        if not system_prompt:
            system_prompt = """Eres un asistente de ventas profesional para una empresa de construcción.
Tu objetivo es:
1. Responder consultas sobre proyectos y servicios
2. Agendar reuniones y visitas
3. Proporcionar presupuestos iniciales
4. Mantener un tono amigable y profesional
5. Recopilar información del cliente (nombre, proyecto, ubicación, presupuesto)

Responde de manera concisa y clara en español."""
        
        try:
            if self.provider == "openai":
                return await self._generate_openai(message, context, system_prompt)
            elif self.provider == "anthropic":
                return await self._generate_anthropic(message, context, system_prompt)
            elif self.provider == "ollama":
                return await self._generate_ollama(message, context, system_prompt)
            elif self.provider == "groq":
                return await self._generate_groq(message, context, system_prompt)
            else:
                return "Lo siento, el servicio de IA no está configurado correctamente."
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "Disculpa, estoy teniendo problemas técnicos. ¿Podrías contactar directamente con nuestro equipo?"
    
    async def _generate_openai(self, message: str, context: Optional[str], system_prompt: str) -> str:
        """Generate response using OpenAI."""
        if not self._client:
            self._client = self._get_openai_client()
        
        if not self._client:
            raise Exception("OpenAI client not initialized")
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"Contexto: {context}"})
        
        messages.append({"role": "user", "content": message})
        
        response = self._client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    async def _generate_anthropic(self, message: str, context: Optional[str], system_prompt: str) -> str:
        """Generate response using Anthropic Claude."""
        if not self._client:
            self._client = self._get_anthropic_client()
        
        if not self._client:
            raise Exception("Anthropic client not initialized")
        
        prompt = f"{system_prompt}\n\n"
        if context:
            prompt += f"Contexto: {context}\n\n"
        prompt += f"Usuario: {message}\n\nAsistente:"
        
        response = self._client.completions.create(
            model="claude-2",
            prompt=prompt,
            max_tokens_to_sample=300
        )
        
        return response.completion
    
    async def _generate_ollama(self, message: str, context: Optional[str], system_prompt: str) -> str:
        """Generate response using Ollama (local)."""
        import requests
        
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        
        prompt = f"{system_prompt}\n\n"
        if context:
            prompt += f"Contexto: {context}\n\n"
        prompt += f"Usuario: {message}\n\nAsistente:"
        
        response = requests.post(
            url,
            json={
                "model": "llama2",
                "prompt": prompt,
                "stream": False
            }
        )
        
        return response.json().get("response", "")
    
    async def _generate_groq(self, message: str, context: Optional[str], system_prompt: str) -> str:
        """Generate response using Groq."""
        import requests
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"Contexto: {context}"})
        
        messages.append({"role": "user", "content": message})
        
        response = requests.post(
            url,
            headers=headers,
            json={
                "model": "mixtral-8x7b-32768",
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.7
            }
        )
        
        return response.json()["choices"][0]["message"]["content"]


# Singleton instance
ai_service = AIService()
