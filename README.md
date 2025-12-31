# Sistema de Gestión Empresarial - Backend

API REST desarrollada con FastAPI para gestión empresarial con automatización de WhatsApp.

## Características

- 🔐 **Autenticación JWT** con roles (SuperAdmin, Admin, Manager, User)
- 👥 **Gestión de Usuarios** con permisos granulares
- ⏰ **Sistema de Asistencia** (check-in/check-out)
- 💰 **Gestión de Gastos** con categorías y exportación CSV
- 🏗️ **Gestión de Proyectos** con seguimiento de progreso
- 📱 **Integración WhatsApp** con respuestas automáticas por IA
- 👤 **Gestión de Clientes** con etiquetado automático

## Tecnologías

- **FastAPI** - Framework web moderno
- **SQLAlchemy** - ORM
- **PostgreSQL/SQLite** - Base de datos
- **JWT** - Autenticación
- **Twilio** - WhatsApp (configurable)
- **OpenAI/Anthropic/Ollama** - IA (configurable)

## Instalación

### 1. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Linux/Mac
# o
venv\Scripts\activate  # En Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus configuraciones:

```env
# Database
DATABASE_URL=sqlite:///./app.db

# Security
SECRET_KEY=tu-clave-secreta-muy-segura-aqui
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Provider (openai, anthropic, ollama, groq)
AI_PROVIDER=openai
OPENAI_API_KEY=tu-api-key-aqui

# WhatsApp Provider (twilio, whatsapp-web, baileys)
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=tu-account-sid
TWILIO_AUTH_TOKEN=tu-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### 4. Inicializar base de datos

```bash
python init_db.py
```

Esto creará un usuario superadmin por defecto:
- **Username:** admin
- **Password:** admin123
- ⚠️ **CAMBIAR INMEDIATAMENTE EN PRODUCCIÓN**

### 5. Ejecutar servidor

```bash
# Desarrollo
uvicorn main:app --reload

# Producción
uvicorn main:app --host 0.0.0.0 --port 8000
```

La API estará disponible en: `http://localhost:8000`

## Documentación API

Una vez iniciado el servidor, accede a:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Endpoints Principales

### Autenticación
- `POST /api/auth/register` - Registrar usuario (Admin)
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Info usuario actual

### Usuarios
- `GET /api/users/` - Listar usuarios
- `GET /api/users/{id}` - Obtener usuario
- `PUT /api/users/{id}` - Actualizar usuario
- `DELETE /api/users/{id}` - Eliminar usuario

### Asistencia
- `POST /api/attendance/check-in` - Marcar entrada
- `POST /api/attendance/check-out` - Marcar salida
- `GET /api/attendance/` - Listar registros
- `GET /api/attendance/stats` - Estadísticas

### Gastos
- `POST /api/expenses/` - Crear gasto
- `GET /api/expenses/` - Listar gastos (con filtros)
- `GET /api/expenses/stats` - Estadísticas
- `GET /api/expenses/export/csv` - Exportar CSV

### Proyectos
- `POST /api/projects/` - Crear proyecto
- `GET /api/projects/` - Listar proyectos
- `POST /api/projects/{id}/progress` - Añadir progreso
- `GET /api/projects/{id}/progress` - Ver progreso

### Clientes
- `POST /api/clients/` - Crear cliente
- `GET /api/clients/` - Listar clientes
- `GET /api/clients/{id}/messages` - Ver mensajes WhatsApp
- `POST /api/clients/{id}/send-message` - Enviar mensaje
- `POST /api/clients/whatsapp/webhook` - Webhook WhatsApp

## Roles y Permisos

### SuperAdmin
- Acceso total al sistema

### Admin
- Gestión de usuarios
- Acceso a todas las funcionalidades

### Manager
- Gestión de proyectos, gastos y clientes
- Ver reportes y estadísticas

### User
- Marcar asistencia
- Ver sus propios datos

## Configuración de WhatsApp (Twilio)

1. Crear cuenta en [Twilio](https://www.twilio.com/)
2. Activar WhatsApp Sandbox o número propio
3. Configurar webhook en Twilio:
   - URL: `https://tu-dominio.com/api/clients/whatsapp/webhook`
   - Método: POST
4. Agregar credenciales en `.env`

## Configuración de IA

### OpenAI (Recomendado para producción)
```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Ollama (Gratis, local)
```bash
# Instalar Ollama
curl https://ollama.ai/install.sh | sh

# Descargar modelo
ollama pull llama2

# Configurar
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### Groq (Rápido, tier gratuito)
```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

## Desarrollo

### Estructura del proyecto

```
backend/
├── app/
│   ├── api/
│   │   ├── routes/      # Endpoints
│   │   └── deps.py      # Dependencias
│   ├── core/
│   │   ├── config.py    # Configuración
│   │   ├── database.py  # Base de datos
│   │   └── security.py  # Seguridad
│   ├── models/          # Modelos SQLAlchemy
│   ├── schemas/         # Schemas Pydantic
│   └── services/        # Servicios (IA, WhatsApp)
├── main.py              # Aplicación principal
├── init_db.py           # Script inicialización
└── requirements.txt     # Dependencias
```

### Agregar nuevos endpoints

1. Crear modelo en `app/models/`
2. Crear schema en `app/schemas/`
3. Crear ruta en `app/api/routes/`
4. Incluir router en `main.py`

## Testing

```bash
pytest
```

## Producción

### Usando Docker (recomendado)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Usando systemd

```ini
[Unit]
Description=Sistema Gestión API
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

## Soporte

Para problemas o preguntas, crear un issue en el repositorio.

## Licencia

MIT
