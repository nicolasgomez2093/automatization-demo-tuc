from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.ml_service import ml_service
from pydantic import BaseModel

router = APIRouter()

class PredictionRequest(BaseModel):
    days_ahead: int = 30

class TrainingResponse(BaseModel):
    success: bool
    model_type: Optional[str] = None
    mae: Optional[float] = None
    mse: Optional[float] = None
    r2: Optional[float] = None
    training_samples: Optional[int] = None
    test_samples: Optional[int] = None
    error: Optional[str] = None

@router.post("/train/expense-model", response_model=TrainingResponse)
async def train_expense_model(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Train expense prediction model"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to train models")
    
    try:
        result = ml_service.train_expense_prediction_model(db, current_user.organization_id)
        
        if result["success"]:
            return TrainingResponse(
                success=True,
                model_type=result["model_type"],
                mae=result["mae"],
                mse=result["mse"],
                r2=result["r2"],
                training_samples=result["training_samples"],
                test_samples=result["test_samples"]
            )
        else:
            return TrainingResponse(
                success=False,
                error=result["error"]
            )
    
    except Exception as e:
        return TrainingResponse(
            success=False,
            error=str(e)
        )

@router.post("/predict/expenses")
async def predict_expenses(
    request: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Predict expenses for the next N days"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to make predictions")
    
    try:
        result = ml_service.predict_expenses(db, current_user.organization_id, request.days_ahead)
        
        if result["success"]:
            return {
                "success": True,
                "predictions": result["predictions"],
                "summary": result["summary"]
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

@router.get("/trends/historical")
async def get_historical_trends(
    days_back: int = 180,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get historical trends and analysis"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view trends")
    
    try:
        result = ml_service.get_historical_trends(db, current_user.organization_id, days_back)
        
        if result["success"]:
            return {
                "success": True,
                "trends": result["trends"],
                "analysis_period": result["analysis_period"],
                "data_points": result["data_points"]
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

@router.get("/profitability/projects")
async def get_project_profitability(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get profitability analysis by project"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view profitability")
    
    try:
        result = ml_service.get_project_profitability(db, current_user.organization_id)
        
        if result["success"]:
            return {
                "success": True,
                "projects": result["projects"],
                "summary": result["summary"]
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

@router.get("/dashboard/insights")
async def get_dashboard_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get ML-powered insights for dashboard"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Get multiple analyses
        insights = {}
        
        # Historical trends - convertir a formato serializable
        trends_result = ml_service.get_historical_trends(db, current_user.organization_id, 90)
        if trends_result.get("success"):
            trends = trends_result.get("trends", {})
            # Simplificar trends para evitar problemas de serialización
            insights["trends"] = {
                "expenses_total": trends.get("expenses", {}).get("total_period", 0) if isinstance(trends.get("expenses"), dict) else 0,
                "expenses_avg": trends.get("expenses", {}).get("average_daily", 0) if isinstance(trends.get("expenses"), dict) else 0,
                "attendance_hours": trends.get("attendance", {}).get("total_hours", 0) if isinstance(trends.get("attendance"), dict) else 0
            }
        
        # Project profitability
        profitability_result = ml_service.get_project_profitability(db, current_user.organization_id)
        if profitability_result.get("success"):
            insights["profitability"] = profitability_result.get("projects", [])[:5]  # Top 5
        
        # Short-term prediction
        prediction_result = ml_service.predict_expenses(db, current_user.organization_id, 7)
        if prediction_result.get("success"):
            summary = prediction_result.get("summary", {})
            insights["weekly_prediction"] = {
                "predicted_total": summary.get("predicted_total", 0) if isinstance(summary, dict) else 0,
                "avg_daily": summary.get("avg_daily", 0) if isinstance(summary, dict) else 0
            }
        
        return {
            "success": True,
            "insights": insights,
            "generated_at": "2025-12-30T22:00:00Z"
        }
    
    except Exception as e:
        logger.error(f"Error in dashboard insights: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

# SuperAdmin endpoints
@router.post("/admin/train/expense-model/{organization_id}")
async def admin_train_expense_model(
    organization_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Train expense model for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = ml_service.train_expense_prediction_model(db, organization_id)
        
        if result["success"]:
            return {
                "success": True,
                "organization_id": organization_id,
                "model_type": result["model_type"],
                "mae": result["mae"],
                "mse": result["mse"],
                "r2": result["r2"],
                "training_samples": result["training_samples"],
                "test_samples": result["test_samples"]
            }
        else:
            return {
                "success": False,
                "organization_id": organization_id,
                "error": result["error"]
            }
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }

@router.post("/admin/predict/expenses/{organization_id}")
async def admin_predict_expenses(
    organization_id: int,
    request: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Predict expenses for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = ml_service.predict_expenses(db, organization_id, request.days_ahead)
        
        if result["success"]:
            return {
                "success": True,
                "organization_id": organization_id,
                "predictions": result["predictions"],
                "summary": result["summary"]
            }
        else:
            return {
                "success": False,
                "organization_id": organization_id,
                "error": result["error"]
            }
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }
