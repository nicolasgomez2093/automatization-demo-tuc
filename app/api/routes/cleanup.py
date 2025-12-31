from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.cleanup_service import cleanup_service
from pydantic import BaseModel

router = APIRouter()

class CleanupResponse(BaseModel):
    success: bool
    timestamp: str = None
    summary: dict = None
    operations: dict = None
    error: str = None

@router.post("/perform", response_model=CleanupResponse)
async def perform_cleanup(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform manual cleanup of temporary files and old data"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to perform cleanup")
    
    try:
        result = cleanup_service.manual_cleanup(db)
        
        if result["success"]:
            return CleanupResponse(
                success=True,
                timestamp=result["timestamp"],
                summary=result.get("summary"),
                operations=result.get("operations")
            )
        else:
            return CleanupResponse(
                success=False,
                error=result.get("error", "Unknown error occurred")
            )
    
    except Exception as e:
        return CleanupResponse(
            success=False,
            error=str(e)
        )

@router.post("/perform-background")
async def perform_cleanup_background(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform cleanup in background"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to perform cleanup")
    
    # Add cleanup to background tasks
    background_tasks.add_task(cleanup_service.manual_cleanup, db)
    
    return {
        "message": "Cleanup process started in background",
        "status": "running"
    }

@router.get("/status")
async def get_cleanup_status(
    current_user: User = Depends(get_current_user)
):
    """Get cleanup service status and statistics"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        stats = cleanup_service.get_cleanup_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/scheduler/start")
async def start_cleanup_scheduler(
    current_user: User = Depends(get_current_user)
):
    """Start automatic cleanup scheduler"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        cleanup_service.start_scheduler()
        return {
            "message": "Cleanup scheduler started successfully",
            "status": "running"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/scheduler/stop")
async def stop_cleanup_scheduler(
    current_user: User = Depends(get_current_user)
):
    """Stop automatic cleanup scheduler"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        cleanup_service.stop_scheduler()
        return {
            "message": "Cleanup scheduler stopped successfully",
            "status": "stopped"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/operations")
async def get_cleanup_operations(
    current_user: User = Depends(get_current_user)
):
    """Get available cleanup operations and their settings"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        stats = cleanup_service.get_cleanup_stats()
        
        operations = [
            {
                "name": "temp_files",
                "description": "Clean temporary files",
                "max_age_days": stats["temp_file_max_age_days"],
                "enabled": True
            },
            {
                "name": "logs",
                "description": "Clean old log files",
                "max_age_days": stats["log_max_age_days"],
                "enabled": True
            },
            {
                "name": "uploads",
                "description": "Clean orphaned upload files",
                "max_age_days": "N/A",
                "enabled": stats["upload_cleanup_enabled"]
            },
            {
                "name": "backups",
                "description": "Clean old backup files",
                "max_age_days": stats["backup_max_age_days"],
                "enabled": True
            },
            {
                "name": "database",
                "description": "Clean old database records",
                "max_age_days": "730",
                "enabled": True
            }
        ]
        
        return {
            "success": True,
            "operations": operations,
            "scheduler": {
                "running": stats["scheduler_running"],
                "interval_hours": stats["cleanup_interval_hours"],
                "next_cleanup": stats["next_cleanup"]
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/operation/{operation_name}")
async def perform_specific_operation(
    operation_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform a specific cleanup operation"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    valid_operations = ["temp_files", "logs", "uploads", "backups", "database"]
    
    if operation_name not in valid_operations:
        raise HTTPException(status_code=400, detail=f"Invalid operation. Valid operations: {valid_operations}")
    
    try:
        # Add specific operation to background tasks
        def perform_operation():
            result = {}
            if operation_name == "temp_files":
                result = cleanup_service.cleanup_temp_files()
            elif operation_name == "logs":
                result = cleanup_service.cleanup_old_logs()
            elif operation_name == "uploads":
                result = cleanup_service.cleanup_orphaned_uploads(db)
            elif operation_name == "backups":
                result = cleanup_service.cleanup_old_backups()
            elif operation_name == "database":
                result = cleanup_service.cleanup_database_records(db)
            
            return result
        
        background_tasks.add_task(perform_operation)
        
        return {
            "message": f"Operation '{operation_name}' started in background",
            "operation": operation_name,
            "status": "running"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
