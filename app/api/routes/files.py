from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from typing import List
from app.services.file_service import file_service
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    prefix: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Upload a single file.
    Files are isolated by organization.
    """
    result = await file_service.upload_file(
        file=file,
        prefix=prefix,
        organization_id=current_user.organization_id
    )
    return result


@router.post("/upload-multiple", status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    prefix: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Upload multiple files at once.
    Useful for project images, documents, etc.
    """
    results = await file_service.upload_multiple(
        files=files,
        prefix=prefix,
        organization_id=current_user.organization_id
    )
    return {
        "total": len(results),
        "successful": len([r for r in results if "error" not in r]),
        "failed": len([r for r in results if "error" in r]),
        "files": results
    }


@router.delete("/delete")
async def delete_file(
    file_url: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a file from storage.
    Only works for files belonging to user's organization.
    """
    # Verify file belongs to user's organization
    if f"org_{current_user.organization_id}" not in file_url:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete files from other organizations"
        )
    
    file_service.delete_file(file_url)
    return {"message": "File deleted successfully"}


@router.get("/info")
async def get_file_info(
    file_url: str,
    current_user: User = Depends(get_current_user)
):
    """Get information about a file."""
    # In a real implementation, you'd query file metadata from DB
    return {
        "url": file_url,
        "organization_id": current_user.organization_id
    }
