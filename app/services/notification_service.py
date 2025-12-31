import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.expense import Expense
from app.models.attendance import Attendance
from app.models.project import Project

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Load notification templates"""
        return {
            'expense_created': {
                'title': 'Nuevo Gasto Registrado',
                'body': 'Se ha registrado un nuevo gasto de ${amount} en la categoría {category}',
                'icon': '💰',
                'actions': [
                    {'action': 'view', 'title': 'Ver Detalle'}
                ]
            },
            'expense_high': {
                'title': '⚠️ Gasto Elevado Detectado',
                'body': 'Se ha detectado un gasto elevado de ${amount} que excede el presupuesto',
                'icon': '⚠️',
                'priority': 'high',
                'actions': [
                    {'action': 'review', 'title': 'Revisar'},
                    {'action': 'approve', 'title': 'Aprobar'}
                ]
            },
            'attendance_reminder': {
                'title': '⏰ Recordatorio de Check-in',
                'body': 'No olvides registrar tu entrada hoy',
                'icon': '⏰',
                'actions': [
                    {'action': 'checkin', 'title': 'Check-in Ahora'}
                ]
            },
            'attendance_checkout_reminder': {
                'title': '⏰ Recordatorio de Check-out',
                'body': 'No olvides registrar tu salida antes de irte',
                'icon': '⏰',
                'actions': [
                    {'action': 'checkout', 'title': 'Check-out Ahora'}
                ]
            },
            'project_deadline': {
                'title': '📅 Fecha Límite Próxima',
                'body': 'El proyecto {project_name} tiene una fecha límite en {days} días',
                'icon': '📅',
                'priority': 'high',
                'actions': [
                    {'action': 'view', 'title': 'Ver Proyecto'}
                ]
            },
            'budget_exceeded': {
                'title': '🚨 Presupuesto Excedido',
                'body': 'El presupuesto del proyecto {project_name} ha sido excedido en {exceeded_amount}',
                'icon': '🚨',
                'priority': 'high',
                'actions': [
                    {'action': 'review', 'title': 'Revisar Presupuesto'},
                    {'action': 'adjust', 'title': 'Ajustar'}
                ]
            },
            'weekly_summary': {
                'title': '📊 Resumen Semanal',
                'body': 'Esta semana registraste {total_hours} horas y ${total_expenses} en gastos',
                'icon': '📊',
                'actions': [
                    {'action': 'view_report', 'title': 'Ver Reporte'}
                ]
            },
            'monthly_summary': {
                'title': '📈 Resumen Mensual',
                'body': 'Este mes registraste {total_hours} horas y ${total_expenses} en gastos',
                'icon': '📈',
                'actions': [
                    {'action': 'view_report', 'title': 'Ver Reporte'}
                ]
            },
            'system_maintenance': {
                'title': '🔧 Mantenimiento del Sistema',
                'body': 'El sistema estará en mantenimiento desde {start_time} hasta {end_time}',
                'icon': '🔧',
                'priority': 'high',
                'actions': []
            },
            'backup_completed': {
                'title': '✅ Backup Completado',
                'body': 'El backup de datos se ha completado exitosamente',
                'icon': '✅',
                'actions': [
                    {'action': 'view', 'title': 'Ver Detalles'}
                ]
            },
            'new_feature': {
                'title': '🎉 Nueva Funcionalidad',
                'body': 'Hemos lanzado una nueva funcionalidad: {feature_name}',
                'icon': '🎉',
                'actions': [
                    {'action': 'learn_more', 'title': 'Saber Más'},
                    {'action': 'try_now', 'title': 'Probar Ahora'}
                ]
            }
        }
    
    def create_notification(
        self,
        template_key: str,
        data: Dict,
        recipients: List[str],
        priority: str = 'normal',
        scheduled_for: Optional[datetime] = None
    ) -> Dict:
        """Create a notification from template"""
        try:
            if template_key not in self.templates:
                return {
                    "success": False,
                    "error": f"Template '{template_key}' not found"
                }
            
            template = self.templates[template_key]
            
            # Format template with data
            title = template['title'].format(**data)
            body = template['body'].format(**data)
            
            notification = {
                "id": f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(title) % 10000}",
                "title": title,
                "body": body,
                "icon": template.get('icon', '📢'),
                "priority": template.get('priority', priority),
                "actions": template.get('actions', []),
                "data": data,
                "created_at": datetime.now().isoformat(),
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "recipients": recipients,
                "read": False,
                "type": template_key
            }
            
            return {
                "success": True,
                "notification": notification
            }
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_notification(self, notification: Dict) -> Dict:
        """Send notification to recipients"""
        try:
            # In a real implementation, this would integrate with:
            # - Push notification services (Firebase, OneSignal, etc.)
            # - Email services
            # - SMS services
            # - WebSocket for real-time delivery
            
            # For now, we'll simulate the sending process
            sent_count = len(notification['recipients'])
            
            # Log the notification
            logger.info(f"Notification sent to {sent_count} recipients: {notification['title']}")
            
            # Store notification history (in real implementation)
            # This would go to a notifications table in the database
            
            return {
                "success": True,
                "sent_count": sent_count,
                "notification_id": notification['id'],
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_and_send(
        self,
        template_key: str,
        data: Dict,
        recipients: List[str],
        priority: str = 'normal',
        scheduled_for: Optional[datetime] = None
    ) -> Dict:
        """Create and send notification in one step"""
        # Create notification
        create_result = self.create_notification(
            template_key, data, recipients, priority, scheduled_for
        )
        
        if not create_result["success"]:
            return create_result
        
        # Send notification
        send_result = self.send_notification(create_result["notification"])
        
        return {
            "success": send_result["success"],
            "notification": create_result["notification"],
            "sent_count": send_result.get("sent_count", 0),
            "error": send_result.get("error")
        }
    
    def get_user_notifications(self, user_id: int, db: Session, unread_only: bool = False) -> List[Dict]:
        """Get notifications for a specific user"""
        try:
            # In real implementation, this would query the notifications table
            # For now, return empty list
            notifications = []
            
            return notifications
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []
    
    def mark_notification_read(self, notification_id: str, user_id: int, db: Session) -> Dict:
        """Mark notification as read"""
        try:
            # In real implementation, update the notification in database
            return {
                "success": True,
                "notification_id": notification_id,
                "marked_read_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_notification_templates(self) -> Dict:
        """Get all available notification templates"""
        return {
            "success": True,
            "templates": self.templates
        }
    
    def create_custom_notification(
        self,
        title: str,
        body: str,
        recipients: List[str],
        icon: str = '📢',
        priority: str = 'normal',
        actions: List[Dict] = None,
        data: Dict = None
    ) -> Dict:
        """Create a custom notification without template"""
        try:
            notification = {
                "id": f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(title) % 10000}",
                "title": title,
                "body": body,
                "icon": icon,
                "priority": priority,
                "actions": actions or [],
                "data": data or {},
                "created_at": datetime.now().isoformat(),
                "recipients": recipients,
                "read": False,
                "type": "custom"
            }
            
            return {
                "success": True,
                "notification": notification
            }
            
        except Exception as e:
            logger.error(f"Error creating custom notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_notification_stats(self, db: Session, organization_id: int) -> Dict:
        """Get notification statistics for an organization"""
        try:
            # In real implementation, this would query the notifications table
            stats = {
                "total_sent": 0,
                "total_read": 0,
                "pending": 0,
                "by_type": {},
                "by_priority": {
                    "high": 0,
                    "normal": 0,
                    "low": 0
                },
                "recent_activity": []
            }
            
            return {
                "success": True,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Automated notification methods
    def check_and_send_expense_alerts(self, db: Session, organization_id: int) -> Dict:
        """Check for expense alerts and send notifications"""
        try:
            alerts_sent = 0
            
            # Get recent expenses
            recent_expenses = db.query(Expense).filter(
                Expense.organization_id == organization_id,
                Expense.created_at >= datetime.now() - timedelta(hours=24)
            ).all()
            
            # Check for high expenses (example: > $10,000)
            high_expense_threshold = 10000
            
            for expense in recent_expenses:
                if expense.amount > high_expense_threshold:
                    # Get admin users
                    admin_users = db.query(User).filter(
                        User.organization_id == organization_id,
                        User.role.in_(['admin', 'superadmin'])
                    ).all()
                    
                    recipients = [user.email for user in admin_users if user.email]
                    
                    if recipients:
                        result = self.create_and_send(
                            'expense_high',
                            {
                                'amount': f"${expense.amount:,.2f}",
                                'description': expense.description,
                                'category': expense.category
                            },
                            recipients,
                            priority='high'
                        )
                        
                        if result["success"]:
                            alerts_sent += 1
            
            return {
                "success": True,
                "alerts_sent": alerts_sent,
                "checked_expenses": len(recent_expenses)
            }
            
        except Exception as e:
            logger.error(f"Error checking expense alerts: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_weekly_summary(self, db: Session, organization_id: int) -> Dict:
        """Send weekly summary notification"""
        try:
            # Calculate weekly stats
            week_ago = datetime.now() - timedelta(days=7)
            
            expenses = db.query(Expense).filter(
                Expense.organization_id == organization_id,
                Expense.created_at >= week_ago
            ).all()
            
            attendances = db.query(Attendance).filter(
                Attendance.organization_id == organization_id,
                Attendance.check_in >= week_ago
            ).all()
            
            total_expenses = sum(exp.amount for exp in expenses)
            total_hours = sum(att.hours_worked or 0 for att in attendances)
            
            # Get all users in organization
            users = db.query(User).filter(
                User.organization_id == organization_id
            ).all()
            
            recipients = [user.email for user in users if user.email]
            
            if recipients:
                result = self.create_and_send(
                    'weekly_summary',
                    {
                        'total_hours': f"{total_hours:.1f}",
                        'total_expenses': f"${total_expenses:,.2f}",
                        'expense_count': len(expenses),
                        'attendance_count': len(attendances)
                    },
                    recipients
                )
                
                return result
            
            return {
                "success": True,
                "message": "No recipients found"
            }
            
        except Exception as e:
            logger.error(f"Error sending weekly summary: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global notification service instance
notification_service = NotificationService()
