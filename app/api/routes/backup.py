from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.backup_service import backup_service
from pydantic import BaseModel
import os

router = APIRouter()

class BackupResponse(BaseModel):
    success: bool
    backup_name: Optional[str] = None
    size: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None

class RestoreRequest(BaseModel):
    backup_name: str

@router.post("/create", response_model=BackupResponse)
async def create_backup(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a backup of the organization's data"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to create backups")
    
    try:
        # Create backup for the organization
        result = backup_service.create_backup(db, current_user.organization_id)
        
        if result["success"]:
            return BackupResponse(
                success=True,
                backup_name=result["backup_name"],
                size=result["size"],
                created_at=result["created_at"]
            )
        else:
            return BackupResponse(
                success=False,
                error=result["error"]
            )
    
    except Exception as e:
        return BackupResponse(
            success=False,
            error=str(e)
        )

@router.post("/create-full")
async def create_full_backup(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a full backup (SuperAdmin only)"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        # Create full backup without organization filter
        result = backup_service.create_backup(db)
        
        if result["success"]:
            return {
                "success": True,
                "backup_name": result["backup_name"],
                "size": result["size"],
                "created_at": result["created_at"],
                "message": "Full backup created successfully"
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/list")
async def list_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available backups"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view backups")
    
    organization_id = None if current_user.role == "superadmin" else current_user.organization_id
    backups = backup_service.list_backups(organization_id)
    
    return {
        "backups": backups,
        "count": len(backups)
    }

@router.post("/restore")
async def restore_backup(
    request: RestoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restore data from backup"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to restore backups")
    
    try:
        # Find backup file
        backup_path = None
        backup_dir = backup_service.backup_dir
        
        for file in os.listdir(backup_dir):
            if file == request.backup_name:
                backup_path = os.path.join(backup_dir, file)
                break
        
        if not backup_path:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Verify backup belongs to organization (unless SuperAdmin)
        if current_user.role != "superadmin":
            if f"_org_{current_user.organization_id}" not in request.backup_name:
                raise HTTPException(status_code=403, detail="Access denied to this backup")
        
        # Add restore to background tasks
        background_tasks.add_task(
            backup_service.restore_backup,
            backup_path=backup_path,
            db=db
        )
        
        return {
            "message": "Restore process started. This may take several minutes.",
            "backup_name": request.backup_name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.delete("/delete/{backup_name}")
async def delete_backup(
    backup_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a backup"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete backups")
    
    try:
        # Find backup file
        backup_path = None
        backup_dir = backup_service.backup_dir
        
        for file in os.listdir(backup_dir):
            if file == backup_name:
                backup_path = os.path.join(backup_dir, file)
                break
        
        if not backup_path:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Verify backup belongs to organization (unless SuperAdmin)
        if current_user.role != "superadmin":
            if f"_org_{current_user.organization_id}" not in backup_name:
                raise HTTPException(status_code=403, detail="Access denied to this backup")
        
        # Delete backup
        if os.path.isdir(backup_path):
            import shutil
            shutil.rmtree(backup_path)
        else:
            os.remove(backup_path)
        
        return {
            "message": f"Backup '{backup_name}' deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/download/{backup_name}")
async def download_backup(
    backup_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get download URL for backup"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to download backups")
    
    try:
        # Find backup file
        backup_path = None
        backup_dir = backup_service.backup_dir
        
        for file in os.listdir(backup_dir):
            if file == backup_name:
                backup_path = os.path.join(backup_dir, file)
                break
        
        if not backup_path:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Verify backup belongs to organization (unless SuperAdmin)
        if current_user.role != "superadmin":
            if f"_org_{current_user.organization_id}" not in backup_name:
                raise HTTPException(status_code=403, detail="Access denied to this backup")
        
        # In a real implementation, you would return a presigned URL or serve the file
        # For now, we'll return the file info
        file_size = os.path.getsize(backup_path)
        
        return {
            "message": "Use the file system to download the backup",
            "backup_path": backup_path,
            "file_size": file_size,
            "backup_name": backup_name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/status")
async def backup_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get backup service status and statistics"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    organization_id = None if current_user.role == "superadmin" else current_user.organization_id
    backups = backup_service.list_backups(organization_id)
    
    # Calculate statistics
    total_size = 0
    backup_count = len(backups)
    
    for backup in backups:
        # Parse size string to bytes (simplified)
        size_str = backup["size"]
        if "KB" in size_str:
            total_size += float(size_str.replace(" KB", "")) * 1024
        elif "MB" in size_str:
            total_size += float(size_str.replace(" MB", "")) * 1024 * 1024
        elif "GB" in size_str:
            total_size += float(size_str.replace(" GB", "")) * 1024 * 1024 * 1024
    
    return {
        "backup_count": backup_count,
        "total_size": f"{total_size / (1024*1024):.1f} MB",
        "backup_directory": backup_service.backup_dir,
        "max_backups": backup_service.max_backups,
        "compression": backup_service.compression,
        "latest_backup": backups[0] if backups else None
    }

# SuperAdmin endpoints
@router.post("/admin/restore/{organization_id}")
async def admin_restore_backup(
    organization_id: int,
    request: RestoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Restore backup for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        # Find backup file
        backup_path = None
        backup_dir = backup_service.backup_dir
        
        for file in os.listdir(backup_dir):
            if file == request.backup_name:
                backup_path = os.path.join(backup_dir, file)
                break
        
        if not backup_path:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Add restore to background tasks
        background_tasks.add_task(
            backup_service.restore_backup,
            backup_path=backup_path,
            db=db
        )
        
        return {
            "message": f"Restore process started for organization {organization_id}. This may take several minutes.",
            "backup_name": request.backup_name,
            "organization_id": organization_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
