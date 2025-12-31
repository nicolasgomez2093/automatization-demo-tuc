from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.notification_service import notification_service
from pydantic import BaseModel

router = APIRouter()

class CustomNotificationRequest(BaseModel):
    title: str
    body: str
    recipients: List[str]
    icon: str = '📢'
    priority: str = 'normal'
    actions: Optional[List[dict]] = None
    data: Optional[dict] = None

class TemplateNotificationRequest(BaseModel):
    template_key: str
    data: dict
    recipients: List[str]
    priority: str = 'normal'
    scheduled_for: Optional[datetime] = None

@router.post("/send/custom")
async def send_custom_notification(
    request: CustomNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send custom notification"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to send notifications")
    
    try:
        # Create custom notification
        create_result = notification_service.create_custom_notification(
            title=request.title,
            body=request.body,
            recipients=request.recipients,
            icon=request.icon,
            priority=request.priority,
            actions=request.actions,
            data=request.data
        )
        
        if not create_result["success"]:
            return {
                "success": False,
                "error": create_result["error"]
            }
        
        # Send notification
        send_result = notification_service.send_notification(create_result["notification"])
        
        return {
            "success": send_result["success"],
            "notification_id": create_result["notification"]["id"],
            "sent_count": send_result.get("sent_count", 0),
            "error": send_result.get("error")
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/send/template")
async def send_template_notification(
    request: TemplateNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send notification from template"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to send notifications")
    
    try:
        result = notification_service.create_and_send(
            template_key=request.template_key,
            data=request.data,
            recipients=request.recipients,
            priority=request.priority,
            scheduled_for=request.scheduled_for
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/templates")
async def get_notification_templates(
    current_user: User = Depends(get_current_user)
):
    """Get available notification templates"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return notification_service.get_notification_templates()

@router.get("/my-notifications")
async def get_my_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get notifications for current user"""
    try:
        notifications = notification_service.get_user_notifications(
            current_user.id, db, unread_only
        )
        
        return {
            "success": True,
            "notifications": notifications,
            "count": len(notifications)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark notification as read"""
    try:
        result = notification_service.mark_notification_read(
            notification_id, current_user.id, db
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/stats")
async def get_notification_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get notification statistics"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = notification_service.get_notification_stats(
            db, current_user.organization_id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/automated/expense-alerts")
async def trigger_expense_alerts(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger automated expense alerts"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = notification_service.check_and_send_expense_alerts(
            db, current_user.organization_id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/automated/weekly-summary")
async def trigger_weekly_summary(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger weekly summary notifications"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = notification_service.send_weekly_summary(
            db, current_user.organization_id
        )
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/test")
async def test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send test notification to current user"""
    try:
        if not current_user.email:
            return {
                "success": False,
                "error": "User email not configured"
            }
        
        result = notification_service.create_and_send(
            'new_feature',
            {
                'feature_name': 'Sistema de Notificaciones',
                'description': 'Prueba del nuevo sistema de notificaciones automáticas'
            },
            [current_user.email],
            priority='normal'
        )
        
        return {
            "success": True,
            "message": "Test notification sent",
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# SuperAdmin endpoints
@router.post("/admin/send-custom/{organization_id}")
async def admin_send_custom_notification(
    organization_id: int,
    request: CustomNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Send custom notification to any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        # Create custom notification
        create_result = notification_service.create_custom_notification(
            title=request.title,
            body=request.body,
            recipients=request.recipients,
            icon=request.icon,
            priority=request.priority,
            actions=request.actions,
            data=request.data
        )
        
        if not create_result["success"]:
            return {
                "success": False,
                "error": create_result["error"]
            }
        
        # Send notification
        send_result = notification_service.send_notification(create_result["notification"])
        
        return {
            "success": send_result["success"],
            "organization_id": organization_id,
            "notification_id": create_result["notification"]["id"],
            "sent_count": send_result.get("sent_count", 0),
            "error": send_result.get("error")
        }
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }

@router.post("/admin/automated/expense-alerts/{organization_id}")
async def admin_trigger_expense_alerts(
    organization_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Trigger automated expense alerts for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = notification_service.check_and_send_expense_alerts(
            db, organization_id
        )
        
        return {
            "success": result["success"],
            "organization_id": organization_id,
            "alerts_sent": result.get("alerts_sent", 0),
            "error": result.get("error")
        }
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }
