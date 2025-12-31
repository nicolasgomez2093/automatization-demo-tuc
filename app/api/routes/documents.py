from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.document import Document, DocumentStatus, DocumentType
from app.services.document_service import document_service
from app.services.file_service import file_service
from pydantic import BaseModel

router = APIRouter()

class DocumentVersionRequest(BaseModel):
    changelog: Optional[str] = None

class DocumentSignRequest(BaseModel):
    signature_data: str
    signature_type: str = "digital"
    legal_statement: Optional[str] = None

class ApprovalWorkflowRequest(BaseModel):
    approvers: List[dict]  # List of {user_id, role, requires_signature, requires_review}

class ApprovalProcessRequest(BaseModel):
    approved: bool
    comments: Optional[str] = None

class ConsultantUtilizationRequest(BaseModel):
    consultant_id: int
    period_start: datetime
    period_end: datetime

class ProjectProfitabilityRequest(BaseModel):
    project_id: int
    period_start: datetime
    period_end: datetime

@router.post("/upload")
async def upload_document(
    title: str = Form(...),
    description: str = Form(""),
    document_type: DocumentType = Form(...),
    project_id: Optional[int] = Form(None),
    client_id: Optional[int] = Form(None),
    tags: str = Form("[]"),
    encrypt_file: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a new document"""
    try:
        # Upload file
        file_result = await file_service.upload_file(file, "documents")
        if not file_result["success"]:
            return file_result
        
        # Parse tags
        import json
        tags_list = json.loads(tags) if tags else []
        
        # Create document record
        result = document_service.upload_document(
            db=db,
            organization_id=current_user.organization_id,
            title=title,
            description=description,
            document_type=document_type,
            file_path=file_result["file_path"],
            filename=file_result["filename"],
            file_size=file_result["file_size"],
            mime_type=file_result["mime_type"],
            user_id=current_user.id,
            project_id=project_id,
            client_id=client_id,
            tags=tags_list,
            encrypt_file=encrypt_file
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/list")
async def list_documents(
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    project_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List documents"""
    try:
        query = db.query(Document).filter(
            Document.organization_id == current_user.organization_id,
            Document.is_latest_version == True
        )
        
        if status:
            query = query.filter(Document.status == status)
        
        if document_type:
            query = query.filter(Document.document_type == document_type)
        
        if project_id:
            query = query.filter(Document.project_id == project_id)
        
        if client_id:
            query = query.filter(Document.client_id == client_id)
        
        documents = query.order_by(Document.created_at.desc()).all()
        
        return {
            "success": True,
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "description": doc.description,
                    "type": doc.document_type.value,
                    "status": doc.status.value,
                    "filename": doc.filename,
                    "file_size": doc.file_size,
                    "version": doc.version,
                    "is_encrypted": doc.is_encrypted,
                    "tags": doc.tags,
                    "project_id": doc.project_id,
                    "client_id": doc.client_id,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat()
                }
                for doc in documents
            ]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get document details"""
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "document": {
                "id": document.id,
                "title": document.title,
                "description": document.description,
                "type": document.document_type.value,
                "status": document.status.value,
                "filename": document.filename,
                "file_size": document.file_size,
                "mime_type": document.mime_type,
                "version": document.version,
                "is_encrypted": document.is_encrypted,
                "tags": document.tags,
                "metadata": document.document_metadata,
                "project_id": document.project_id,
                "client_id": document.client_id,
                "user_id": document.user_id,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "expires_at": document.expires_at.isoformat() if document.expires_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/{document_id}/version")
async def create_document_version(
    document_id: int,
    changelog: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new version of a document"""
    try:
        # Verify document exists and belongs to organization
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Upload new file
        file_result = await file_service.upload_file(file, "documents")
        if not file_result["success"]:
            return file_result
        
        # Create new version
        result = document_service.create_document_version(
            db=db,
            document_id=document_id,
            file_path=file_result["file_path"],
            filename=file_result["filename"],
            file_size=file_result["file_size"],
            user_id=current_user.id,
            changelog=changelog
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all versions of a document"""
    try:
        # Verify document exists and belongs to organization
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        result = document_service.get_document_versions(db, document_id)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/{document_id}/sign")
async def sign_document(
    document_id: int,
    request: DocumentSignRequest,
    request_obj: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sign a document digitally"""
    try:
        # Verify document exists and belongs to organization
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get client IP and user agent
        client_ip = request_obj.client.host
        user_agent = request_obj.headers.get("user-agent", "")
        
        result = document_service.sign_document(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            signature_data=request.signature_data,
            signature_type=request.signature_type,
            ip_address=client_ip,
            user_agent=user_agent,
            legal_statement=request.legal_statement
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/{document_id}/approval-workflow")
async def create_approval_workflow(
    document_id: int,
    request: ApprovalWorkflowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create approval workflow for document"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to create approval workflows")
    
    try:
        # Verify document exists and belongs to organization
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        result = document_service.create_approval_workflow(
            db=db,
            document_id=document_id,
            approvers=request.approvers,
            created_by=current_user.id
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/approval/{approval_id}/process")
async def process_approval(
    approval_id: int,
    request: ApprovalProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process document approval/rejection"""
    try:
        result = document_service.process_approval(
            db=db,
            approval_id=approval_id,
            user_id=current_user.id,
            approved=request.approved,
            comments=request.comments
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/consultant-utilization")
async def calculate_consultant_utilization(
    request: ConsultantUtilizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate resource utilization for consultant"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = document_service.calculate_consultant_utilization(
            db=db,
            organization_id=current_user.organization_id,
            consultant_id=request.consultant_id,
            period_start=request.period_start,
            period_end=request.period_end
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/project-profitability")
async def calculate_project_profitability(
    request: ProjectProfitabilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate project profitability"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = document_service.calculate_project_profitability(
            db=db,
            organization_id=current_user.organization_id,
            project_id=request.project_id,
            period_start=request.period_start,
            period_end=request.period_end
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/organization-kpis")
async def calculate_organization_kpis(
    period_start: datetime,
    period_end: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate real-time KPIs for organization"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = document_service.calculate_organization_kpis(
            db=db,
            organization_id=current_user.organization_id,
            period_start=period_start,
            period_end=period_end
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/team-productivity")
async def calculate_team_productivity(
    period_start: datetime,
    period_end: datetime,
    team_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate productivity metrics for team or user"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = document_service.calculate_team_productivity(
            db=db,
            organization_id=current_user.organization_id,
            period_start=period_start,
            period_end=period_end,
            team_id=team_id,
            user_id=user_id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    version: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download document"""
    try:
        # Get document (or specific version)
        if version:
            document = db.query(Document).filter(
                Document.parent_document_id == document_id,
                Document.version == version,
                Document.organization_id == current_user.organization_id
            ).first()
        else:
            document = db.query(Document).filter(
                Document.id == document_id,
                Document.organization_id == current_user.organization_id
            ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Decrypt file if necessary
        file_path = document.file_path
        if document.is_encrypted:
            # This would decrypt the file before download
            pass
        
        # Return file for download
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            filename=document.filename,
            media_type=document.mime_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# SuperAdmin endpoints
@router.post("/admin/organization-kpis/{organization_id}")
async def admin_calculate_organization_kpis(
    organization_id: int,
    period_start: datetime,
    period_end: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Calculate KPIs for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = document_service.calculate_organization_kpis(
            db=db,
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end
        )
        
        if result["success"]:
            result["organization_id"] = organization_id
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }
