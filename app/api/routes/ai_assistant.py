from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.ai_assistant_service import ai_assistant_service
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    context_type: str = "general"  # 'general', 'project_status', 'resource_optimization', 'financial_analysis'

class ReportRequest(BaseModel):
    project_id: Optional[int] = None
    report_type: str = "comprehensive"  # 'comprehensive', 'financial', 'operational', 'summary'

class PredictiveAnalysisRequest(BaseModel):
    prediction_period: int = 30  # days

class OptimizationRequest(BaseModel):
    analysis_period: int = 30  # days

@router.post("/chat")
async def chat_with_assistant(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chat principal con el asistente de IA"""
    try:
        result = await ai_assistant_service.chat_with_assistant(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            message=request.message,
            context_type=request.context_type
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fallback_response": "Lo siento, estoy teniendo dificultades para procesar tu solicitud. Por favor, intenta nuevamente más tarde."
        }

@router.post("/generate-report")
async def generate_ai_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generación automática de informes con IA"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to generate reports")
    
    try:
        result = await ai_assistant_service.generate_project_report(
            db=db,
            organization_id=current_user.organization_id,
            project_id=request.project_id,
            report_type=request.report_type
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/predictive-expense-analysis")
async def predictive_expense_analysis(
    request: PredictiveAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Análisis predictivo de gastos con IA"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to access predictive analysis")
    
    try:
        result = await ai_assistant_service.predictive_expense_analysis(
            db=db,
            organization_id=current_user.organization_id,
            prediction_period=request.prediction_period
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/resource-optimization")
async def resource_optimization_suggestions(
    request: OptimizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sugerencias de optimización de recursos con IA"""
    logger.info(f"Resource optimization request from user {current_user.id}, period {request.analysis_period}")
    
    if current_user.role not in ["admin", "superadmin"]:
        logger.warning(f"Unauthorized optimization attempt by user {current_user.id} with role {current_user.role}")
        raise HTTPException(status_code=403, detail="Not authorized to access optimization analysis")
    
    try:
        result = await ai_assistant_service.resource_optimization_suggestions(
            db=db,
            organization_id=current_user.organization_id,
            analysis_period=request.analysis_period
        )
        
        logger.info(f"Resource optimization result: success={result.get('success')}")
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/quick-insights")
async def get_quick_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener insights rápidos para el dashboard"""
    try:
        # Obtener datos básicos para insights rápidos
        from app.models.project import Project
        from app.models.expense import Expense
        from app.models.attendance import Attendance
        from sqlalchemy import func, and_
        from datetime import timedelta
        
        # Proyectos activos
        active_projects = db.query(Project).filter(
            Project.organization_id == current_user.organization_id,
            Project.status == 'active'
        ).count()
        
        # Gastos del último mes
        last_month = datetime.utcnow() - timedelta(days=30)
        total_expenses = db.query(func.sum(Expense.amount)).filter(
            Expense.organization_id == current_user.organization_id,
            Expense.created_at >= last_month
        ).scalar() or 0
        
        # Horas trabajadas última semana
        last_week = datetime.utcnow() - timedelta(days=7)
        total_hours = db.query(func.sum(Attendance.hours_worked)).filter(
            Attendance.organization_id == current_user.organization_id,
            Attendance.check_in >= last_week
        ).scalar() or 0
        
        # Generar insights simples
        insights = []
        
        if total_expenses > 100000:
            insights.append({
                "type": "warning",
                "title": "Gastos elevados",
                "message": f"Los gastos del último mes suman ${total_expenses:,.0f}. Considera revisar las categorías con mayor crecimiento.",
                "priority": "medium"
            })
        
        if total_hours < 160:
            insights.append({
                "type": "info",
                "title": "Productividad",
                "message": f"Las horas trabajadas esta semana son {total_hours:.1f}. Hay oportunidad para mejorar la productividad.",
                "priority": "low"
            })
        
        if active_projects > 5:
            insights.append({
                "type": "success",
                "title": "Cartera activa",
                "message": f"Tienes {active_projects} proyectos activos. Excelente nivel de actividad!",
                "priority": "low"
            })
        
        return {
            "success": True,
            "insights": insights,
            "metrics": {
                "active_projects": active_projects,
                "monthly_expenses": total_expenses,
                "weekly_hours": total_hours
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/suggested-questions")
async def get_suggested_questions(
    context: str = "general",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener preguntas sugeridas para el asistente"""
    try:
        questions = {
            "general": [
                "¿Cuál es el estado general de mis proyectos?",
                "¿Qué gastos han aumentado recientemente?",
                "¿Cómo está la productividad del equipo?",
                "¿Qué proyectos necesitan atención urgente?",
                "¿Cuáles son las principales oportunidades de mejora?"
            ],
            "financial": [
                "¿Cuál es nuestro margen de ganancia actual?",
                "¿Qué categorías de gastos tienen mayor crecimiento?",
                "¿Cómo podemos optimizar nuestros costos?",
                "¿Qué proyectos son más rentables?",
                "¿Cuál es el ROI de nuestros proyectos activos?"
            ],
            "projects": [
                "¿Qué proyectos están en riesgo de retraso?",
                "¿Cuál es el progreso general de los proyectos?",
                "¿Qué recursos necesitan reasignación?",
                "¿Cómo están los presupuestos vs gastos reales?",
                "¿Qué proyectos tienen mejor desempeño?"
            ],
            "resources": [
                "¿Quiénes son los consultores más productivos?",
                "¿Cómo podemos optimizar la utilización de recursos?",
                "¿Hay equipo sobrecargado o subutilizado?",
                "¿Qué habilidades necesitamos desarrollar?",
                "¿Cómo mejorar la eficiencia del equipo?"
            ]
        }
        
        return {
            "success": True,
            "context": context,
            "questions": questions.get(context, questions["general"]),
            "total_questions": len(questions.get(context, questions["general"]))
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/conversation-history")
async def get_conversation_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener historial de conversaciones (si se implementa)"""
    # Por ahora retornar vacío hasta implementar la tabla de conversaciones
    return {
        "success": True,
        "conversations": [],
        "total": 0,
        "message": "Historial de conversaciones no implementado aún"
    }

# SuperAdmin endpoints
@router.post("/admin/chat/{organization_id}")
async def admin_chat_with_assistant(
    organization_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Chat con asistente para cualquier organización"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = await ai_assistant_service.chat_with_assistant(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
            message=request.message,
            context_type=request.context_type
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

@router.post("/admin/generate-report/{organization_id}")
async def admin_generate_ai_report(
    organization_id: int,
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Generar informe para cualquier organización"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = await ai_assistant_service.generate_project_report(
            db=db,
            organization_id=organization_id,
            project_id=request.project_id,
            report_type=request.report_type
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
