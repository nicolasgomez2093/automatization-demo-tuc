from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import get_redis, close_redis
from app.api.routes import auth, users, attendance, expenses, projects, clients, files, organizations, reports, backup, cleanup, ml, notifications, budgets, security, documents, ai_assistant, admin
from app.services.cleanup_service import cleanup_service
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de gestión empresarial con automatización de WhatsApp"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(organizations.router, prefix="/api")
app.include_router(reports.router, prefix="/api/reports")
app.include_router(backup.router, prefix="/api/backup")
app.include_router(cleanup.router, prefix="/api/cleanup")
app.include_router(ml.router, prefix="/api/ml")
app.include_router(notifications.router, prefix="/api/notifications")
app.include_router(budgets.router, prefix="/api/budgets")
app.include_router(security.router, prefix="/api/security")
app.include_router(documents.router, prefix="/api/documents")
app.include_router(ai_assistant.router, prefix="/api/ai-assistant")
app.include_router(admin.router, prefix="/api/admin")

# Mount static files for uploads (only if not using S3)
if not settings.USE_S3:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting up...")
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")
    
    # Start cleanup scheduler
    try:
        cleanup_service.start_scheduler()
        logger.info("✅ Cleanup scheduler started")
    except Exception as e:
        logger.warning(f"⚠️ Cleanup scheduler failed: {e}")
    
    logger.info("✅ Application started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down...")
    cleanup_service.stop_scheduler()
    await close_redis()
    logger.info("✅ Application stopped")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sistema de Gestión Empresarial API",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        redis = await get_redis()
        redis_status = "connected" if await redis.ping() else "disconnected"
    except:
        redis_status = "disconnected"
    
    return {
        "status": "healthy",
        "redis": redis_status,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
