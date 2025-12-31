from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.budget import Budget, BudgetStatus, BudgetType, ExpenseRequest
from app.services.budget_service import budget_service
from pydantic import BaseModel

router = APIRouter()

class BudgetCreateRequest(BaseModel):
    name: str
    description: str
    type: BudgetType
    total_amount: float
    start_date: datetime
    end_date: datetime
    project_id: Optional[int] = None
    warning_threshold: float = 80.0
    critical_threshold: float = 95.0
    requires_approval: bool = False
    approver_id: Optional[int] = None
    max_single_expense: Optional[float] = None

class ExpenseRequestCreate(BaseModel):
    title: str
    description: str
    amount: float
    category: str
    budget_id: Optional[int] = None
    receipt_url: Optional[str] = None
    supporting_documents: Optional[List[str]] = None

class ROIAnalysisRequest(BaseModel):
    project_id: int
    analysis_start_date: datetime
    analysis_end_date: datetime
    total_investment: float
    revenue_streams: List[dict]
    cost_breakdown: List[dict]
    assumptions: str

@router.post("/create")
async def create_budget(
    request: BudgetCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new budget"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to create budgets")
    
    try:
        result = budget_service.create_budget(
            db=db,
            organization_id=current_user.organization_id,
            name=request.name,
            description=request.description,
            budget_type=request.type,
            total_amount=request.total_amount,
            start_date=request.start_date,
            end_date=request.end_date,
            project_id=request.project_id,
            warning_threshold=request.warning_threshold,
            critical_threshold=request.critical_threshold,
            requires_approval=request.requires_approval,
            approver_id=request.approver_id,
            max_single_expense=request.max_single_expense,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/list")
async def list_budgets(
    status: Optional[BudgetStatus] = None,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List budgets for the organization"""
    try:
        query = db.query(Budget).filter(Budget.organization_id == current_user.organization_id)
        
        if status:
            query = query.filter(Budget.status == status)
        
        if project_id:
            query = query.filter(Budget.project_id == project_id)
        
        budgets = query.all()
        
        return {
            "success": True,
            "budgets": [
                {
                    "id": b.id,
                    "name": b.name,
                    "description": b.description,
                    "type": b.type.value,
                    "status": b.status.value,
                    "total_amount": b.total_amount,
                    "spent_amount": b.spent_amount,
                    "remaining_amount": b.remaining_amount,
                    "utilization_percentage": b.utilization_percentage,
                    "start_date": b.start_date.isoformat(),
                    "end_date": b.end_date.isoformat(),
                    "project_id": b.project_id,
                    "is_warning_exceeded": b.is_warning_threshold_exceeded,
                    "is_critical_exceeded": b.is_critical_threshold_exceeded,
                    "is_over_budget": b.is_over_budget
                }
                for b in budgets
            ]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/{budget_id}/status")
async def get_budget_status(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed budget status"""
    try:
        # Verify budget belongs to organization
        budget = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.organization_id == current_user.organization_id
        ).first()
        
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        result = budget_service.get_budget_status(db, budget_id)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/expense-request")
async def create_expense_request(
    request: ExpenseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an expense request for approval"""
    try:
        result = budget_service.create_expense_request(
            db=db,
            organization_id=current_user.organization_id,
            title=request.title,
            description=request.description,
            amount=request.amount,
            category=request.category,
            budget_id=request.budget_id,
            requested_by=current_user.id,
            receipt_url=request.receipt_url,
            supporting_documents=request.supporting_documents
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/expense-requests")
async def list_expense_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List expense requests"""
    try:
        query = db.query(ExpenseRequest).filter(
            ExpenseRequest.organization_id == current_user.organization_id
        )
        
        # Users can only see their own requests unless they're admin
        if current_user.role not in ["admin", "superadmin"]:
            query = query.filter(ExpenseRequest.requested_by == current_user.id)
        
        if status:
            query = query.filter(ExpenseRequest.status == status)
        
        requests = query.order_by(ExpenseRequest.created_at.desc()).all()
        
        return {
            "success": True,
            "requests": [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "amount": r.amount,
                    "category": r.category,
                    "status": r.status,
                    "budget_id": r.budget_id,
                    "requested_by": r.requested_by,
                    "approved_by": r.approved_by,
                    "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                    "rejection_reason": r.rejection_reason,
                    "created_at": r.created_at.isoformat()
                }
                for r in requests
            ]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/expense-request/{request_id}/approve")
async def approve_expense_request(
    request_id: int,
    approved: bool = True,
    rejection_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject an expense request"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to approve requests")
    
    try:
        # Verify request belongs to organization
        expense_request = db.query(ExpenseRequest).filter(
            ExpenseRequest.id == request_id,
            ExpenseRequest.organization_id == current_user.organization_id
        ).first()
        
        if not expense_request:
            raise HTTPException(status_code=404, detail="Expense request not found")
        
        result = budget_service.approve_expense_request(
            db=db,
            request_id=request_id,
            approved_by=current_user.id,
            approved=approved,
            rejection_reason=rejection_reason
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/roi-analysis")
async def create_roi_analysis(
    request: ROIAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create ROI analysis for a project"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to create ROI analysis")
    
    try:
        result = budget_service.calculate_project_roi(
            db=db,
            organization_id=current_user.organization_id,
            project_id=request.project_id,
            analysis_start_date=request.analysis_start_date,
            analysis_end_date=request.analysis_end_date,
            total_investment=request.total_investment,
            revenue_streams=request.revenue_streams,
            cost_breakdown=request.cost_breakdown,
            assumptions=request.assumptions,
            created_by=current_user.id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/dashboard")
async def get_budget_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get budget dashboard data"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = budget_service.get_budget_dashboard(db, current_user.organization_id)
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/{budget_id}/alert/acknowledge")
async def acknowledge_budget_alert(
    budget_id: int,
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge a budget alert"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Verify budget belongs to organization
        budget = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.organization_id == current_user.organization_id
        ).first()
        
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        # Find and acknowledge alert
        from app.models.budget import BudgetAlert
        alert = db.query(BudgetAlert).filter(
            BudgetAlert.id == alert_id,
            BudgetAlert.budget_id == budget_id
        ).first()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        alert.is_acknowledged = True
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Alert acknowledged successfully",
            "acknowledged_at": alert.acknowledged_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# SuperAdmin endpoints
@router.post("/admin/create/{organization_id}")
async def admin_create_budget(
    organization_id: int,
    request: BudgetCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Create budget for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = budget_service.create_budget(
            db=db,
            organization_id=organization_id,
            name=request.name,
            description=request.description,
            budget_type=request.type,
            total_amount=request.total_amount,
            start_date=request.start_date,
            end_date=request.end_date,
            project_id=request.project_id,
            warning_threshold=request.warning_threshold,
            critical_threshold=request.critical_threshold,
            requires_approval=request.requires_approval,
            approver_id=request.approver_id,
            max_single_expense=request.max_single_expense,
            created_by=current_user.id
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

@router.get("/admin/dashboard/{organization_id}")
async def admin_get_budget_dashboard(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Get budget dashboard for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = budget_service.get_budget_dashboard(db, organization_id)
        
        if result["success"]:
            result["organization_id"] = organization_id
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }
