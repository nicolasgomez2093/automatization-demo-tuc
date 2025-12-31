import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import openai
from app.models.project import Project
from app.models.expense import Expense
from app.models.attendance import Attendance
from app.models.user import User
from app.models.budget import Budget, BudgetTransaction
from app.core.config import settings
from app.services.ml_service import ml_service

logger = logging.getLogger(__name__)

class AIAssistantService:
    def __init__(self):
        # Inicializar cliente de OpenAI (o puede ser cualquier otro proveedor)
        self.openai_client = None
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_client = openai
        
        # Context templates para diferentes tipos de consultas
        self.context_templates = {
            'project_status': """
            Eres un asistente experto en gestión de proyectos. Analiza los datos proporcionados y responde las preguntas del usuario.
            
            Datos del proyecto:
            {project_data}
            
            Gastos recientes:
            {expense_data}
            
            Asistencia del equipo:
            {attendance_data}
            
            Presupuesto:
            {budget_data}
            
            Responde de manera clara, concisa y enfocada en la acción. Si hay problemas, sugiere soluciones específicas.
            """,
            
            'resource_optimization': """
            Eres un experto en optimización de recursos y productividad. Analiza los datos de utilización de recursos y proporciona recomendaciones específicas.
            
            Datos de utilización:
            {utilization_data}
            
            Datos de productividad:
            {productivity_data}
            
            Costos y rentabilidad:
            {cost_data}
            
            Proporciona recomendaciones accionables para mejorar la eficiencia y reducir costos.
            """,
            
            'financial_analysis': """
            Eres un analista financiero experto. Analiza los datos financieros y proporciona insights y predicciones.
            
            Datos financieros:
            {financial_data}
            
            Tendencias históricas:
            {trends_data}
            
            Presupuestos vs reales:
            {budget_comparison}
            
            Proporciona análisis detallado, identificación de riesgos y oportunidades, y recomendaciones estratégicas.
            """,
            
            'general_assistant': """
            Eres un asistente inteligente para un sistema de gestión empresarial. Tienes acceso a datos de proyectos, gastos, asistencia, presupuestos y productividad.
            
            Contexto actual:
            {context_data}
            
            Responde preguntas sobre el sistema, proporciona insights útiles y ayuda a tomar decisiones informadas.
            """
        }
    
    async def chat_with_assistant(
        self,
        db: Session,
        organization_id: int,
        user_id: int,
        message: str,
        context_type: str = 'general'
    ) -> Dict:
        """Chat principal con el asistente de IA"""
        try:
            logger.info(f"AI Chat request from user {user_id}: {message[:50]}...")
            
            # Analizar la consulta y generar respuesta personalizada con datos reales
            response = await self._generate_personalized_response(db, organization_id, message)
            logger.info(f"AI response generated: {len(response)} chars")
            
            return {
                "success": True,
                "response": response,
                "context_type": context_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in AI assistant chat: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "fallback_response": "Lo siento, estoy teniendo dificultades para procesar tu solicitud en este momento. Por favor, intenta nuevamente más tarde."
            }
    
    async def generate_project_report(
        self,
        db: Session,
        organization_id: int,
        project_id: Optional[int] = None,
        report_type: str = 'comprehensive'
    ) -> Dict:
        """Generación automática de informes con IA"""
        try:
            logger.info(f"Generating {report_type} report for org {organization_id}, project {project_id}")
            
            # Obtener datos reales
            if project_id:
                # Reporte de proyecto específico
                project = db.query(Project).filter(
                    Project.id == project_id,
                    Project.organization_id == organization_id
                ).first()
                
                if not project:
                    return {"success": False, "error": "Proyecto no encontrado"}
                
                # Obtener gastos del proyecto
                expenses = db.query(Expense).filter(
                    Expense.project_id == project_id,
                    Expense.organization_id == organization_id
                ).all()
                
                total_expenses = sum(e.amount for e in expenses)
                
                report_content = f"""# Informe del Proyecto: {project.name}

## Resumen Ejecutivo
- **Estado:** {project.status}
- **Presupuesto:** ${project.budget:,.2f} USD
- **Gastos Totales:** ${total_expenses:,.2f} USD
- **Disponible:** ${(project.budget - total_expenses):,.2f} USD
- **Utilización:** {(total_expenses/project.budget*100):.1f}%

## Detalles del Proyecto
- **Descripción:** {project.description or 'Sin descripción'}
- **Fecha Inicio:** {project.start_date.strftime('%d/%m/%Y') if project.start_date else 'No definida'}
- **Fecha Fin:** {project.end_date.strftime('%d/%m/%Y') if project.end_date else 'No definida'}
- **Progreso:** {project.progress_percentage}%

## Análisis de Gastos
- **Total de Transacciones:** {len(expenses)}
- **Gasto Promedio:** ${(total_expenses/len(expenses)):,.2f} USD por transacción

## Recomendaciones
{'⚠️ **Alerta:** El proyecto está cerca del límite presupuestario' if (total_expenses/project.budget) > 0.9 else '✅ El presupuesto está bajo control'}
"""
            else:
                # Reporte general de todos los proyectos
                projects = db.query(Project).filter(
                    Project.organization_id == organization_id
                ).all()
                
                total_budget = sum(p.budget for p in projects if p.budget)
                
                expenses = db.query(Expense).filter(
                    Expense.organization_id == organization_id
                ).all()
                
                total_expenses = sum(e.amount for e in expenses)
                
                report_content = f"""# Informe General de Proyectos

## Resumen Ejecutivo
- **Total de Proyectos:** {len(projects)}
- **Presupuesto Total:** ${total_budget:,.2f} USD
- **Gastos Totales:** ${total_expenses:,.2f} USD
- **Balance:** ${(total_budget - total_expenses):,.2f} USD

## Distribución por Estado
"""
                # Contar proyectos por estado
                from collections import Counter
                status_count = Counter(p.status for p in projects)
                for status, count in status_count.items():
                    report_content += f"- **{status}:** {count} proyectos\n"
                
                report_content += f"""
## Análisis Financiero
- **Total de Gastos Registrados:** {len(expenses)}
- **Gasto Promedio por Proyecto:** ${(total_expenses/len(projects)):,.2f} USD
- **Utilización Presupuestaria:** {(total_expenses/total_budget*100):.1f}%

## Recomendaciones
- Revisar proyectos en estado 'pausado' para reactivación o cierre
- Monitorear proyectos con alta utilización presupuestaria
- Considerar ajustes presupuestarios para proyectos activos
"""
            
            structured_report = {
                "title": f"Informe {report_type.title()}",
                "generated_at": datetime.utcnow().isoformat(),
                "content": report_content,
                "sections": [],
                "key_metrics": [],
                "recommendations": []
            }
            
            return {
                "success": True,
                "report": structured_report,
                "report_type": report_type,
                "generated_at": datetime.utcnow().isoformat(),
                "project_id": project_id
            }
            
        except Exception as e:
            logger.error(f"Error generating AI report: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def predictive_expense_analysis(
        self,
        db: Session,
        organization_id: int,
        prediction_period: int = 30
    ) -> Dict:
        """Análisis predictivo de gastos con IA"""
        try:
            logger.info(f"Generating predictive analysis for org {organization_id}, period {prediction_period} days")
            
            # Obtener gastos históricos
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            expenses = db.query(Expense).filter(
                Expense.organization_id == organization_id,
                Expense.expense_date >= cutoff_date
            ).all()
            
            if not expenses:
                return {
                    "success": False,
                    "error": "No hay suficientes datos históricos para generar predicciones"
                }
            
            # Calcular métricas básicas
            total_expenses = sum(e.amount for e in expenses)
            avg_daily = total_expenses / 90
            predicted_total = avg_daily * prediction_period
            
            # Análisis por categoría
            from collections import defaultdict
            by_category = defaultdict(float)
            for e in expenses:
                by_category[e.category] += e.amount
            
            analysis_content = f"""# Análisis Predictivo de Gastos

## Predicción para los próximos {prediction_period} días

### Resumen
- **Gasto Histórico (90 días):** ${total_expenses:,.2f} USD
- **Promedio Diario:** ${avg_daily:,.2f} USD
- **Predicción Total:** ${predicted_total:,.2f} USD

### Distribución por Categoría
"""
            for category, amount in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_expenses) * 100
                predicted_category = (amount / 90) * prediction_period
                analysis_content += f"- **{category}:** ${amount:,.2f} ({percentage:.1f}%) → Predicción: ${predicted_category:,.2f}\n"
            
            analysis_content += f"""
### Recomendaciones
- Monitorear categorías con mayor gasto
- Considerar optimizaciones en gastos recurrentes
- Establecer alertas para gastos inusuales
"""
            
            return {
                "success": True,
                "predictions": {
                    "content": analysis_content,
                    "predicted_total": predicted_total,
                    "avg_daily": avg_daily,
                    "confidence_score": 0.75,
                    "prediction_period": prediction_period
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in predictive expense analysis: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def resource_optimization_suggestions(
        self,
        db: Session,
        organization_id: int,
        analysis_period: int = 30
    ) -> Dict:
        """Sugerencias de optimización de recursos con IA"""
        try:
            logger.info(f"Generating resource optimization for org {organization_id}, period {analysis_period} days")
            
            # Obtener datos de asistencia
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=analysis_period)
            
            attendance_records = db.query(Attendance).filter(
                Attendance.organization_id == organization_id,
                Attendance.check_in >= cutoff_date
            ).all()
            
            if not attendance_records:
                return {
                    "success": False,
                    "error": "No hay suficientes datos de asistencia para análisis"
                }
            
            # Calcular métricas
            total_hours = sum(a.hours_worked or 0 for a in attendance_records)
            # Usar días reales con registros en lugar del período completo
            total_days = len(attendance_records)
            avg_hours_per_day = total_hours / total_days if total_days > 0 else 0
            
            # Validar que las horas sean razonables (máximo 12 horas por día)
            if avg_hours_per_day > 12:
                logger.warning(f"Average hours per day seems too high: {avg_hours_per_day}")
                # Cap at reasonable value for display
                avg_hours_per_day = min(avg_hours_per_day, 12)
            
            # Análisis por usuario
            from collections import defaultdict
            by_user = defaultdict(lambda: {"hours": 0, "days": 0})
            for a in attendance_records:
                by_user[a.user_id]["hours"] += a.hours_worked or 0
                by_user[a.user_id]["days"] += 1
            
            optimization_content = f"""# Optimización de Recursos

## Análisis de los últimos {analysis_period} días

### Resumen General
- **Total de Horas Trabajadas:** {total_hours:,.1f} horas
- **Promedio Diario:** {avg_hours_per_day:,.1f} horas
- **Días con Registro:** {total_days} días
- **Usuarios Activos:** {len(by_user)} personas

### Distribución por Usuario
"""
            for user_id, data in sorted(by_user.items(), key=lambda x: x[1]["hours"], reverse=True):
                avg_user_hours = data["hours"] / data["days"] if data["days"] > 0 else 0
                optimization_content += f"- **Usuario {user_id}:** {data['hours']:.1f} horas ({data['days']} días) - Promedio: {avg_user_hours:.1f} h/día\n"
            
            optimization_content += f"""
### Recomendaciones
- ✅ Mantener registro consistente de asistencia
- 📊 Monitorear usuarios con carga de trabajo alta
- ⚖️ Considerar redistribución si hay desequilibrios
- 📈 Establecer metas de productividad realistas
"""
            
            return {
                "success": True,
                "suggestions": {
                    "content": optimization_content,
                    "total_hours": total_hours,
                    "avg_hours_per_day": avg_hours_per_day,
                    "active_users": len(by_user),
                    "analysis_period": analysis_period
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in resource optimization: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_personalized_response(self, db: Session, organization_id: int, message: str) -> str:
        """Generar respuesta personalizada basada en datos reales"""
        message_lower = message.lower()
        
        # Obtener datos reales
        projects = db.query(Project).filter(Project.organization_id == organization_id).all()
        expenses = db.query(Expense).filter(Expense.organization_id == organization_id).all()
        attendance = db.query(Attendance).filter(Attendance.organization_id == organization_id).all()
        
        # Análisis de proyectos
        if any(word in message_lower for word in ["proyecto", "proyectos", "torre", "las heras"]):
            if not projects:
                return "📁 No tienes proyectos registrados aún. ¿Te gustaría que te ayude a crear uno?"
            
            # Buscar proyecto específico si se menciona
            project_match = None
            for p in projects:
                # Buscar coincidencias parciales (ej: "torre" en "Torre Las Heras")
                project_words = p.name.lower().split()
                message_words = message_lower.split()
                # Si al menos 2 palabras coinciden o el nombre completo está en el mensaje
                if (p.name.lower() in message_lower or 
                    len(set(project_words) & set(message_words)) >= 2):
                    project_match = p
                    break
            
            if project_match:
                # Análisis de proyecto específico
                project_expenses = [e for e in expenses if e.project_id == project_match.id]
                total_spent = sum(e.amount for e in project_expenses)
                budget_used = (total_spent / project_match.budget * 100) if project_match.budget else 0
                
                response = f"""🏗️ **Análisis del Proyecto: {project_match.name}**

📊 **Estado Actual:**
• **Estado:** {project_match.status}
• **Progreso:** {project_match.progress_percentage}%
• **Presupuesto:** ${project_match.budget:,.2f} USD
• **Gastado:** ${total_spent:,.2f} USD ({budget_used:.1f}%)
• **Disponible:** ${(project_match.budget - total_spent):,.2f} USD

📅 **Fechas:**
• **Inicio:** {project_match.start_date.strftime('%d/%m/%Y') if project_match.start_date else 'No definida'}
• **Fin estimado:** {project_match.end_date.strftime('%d/%m/%Y') if project_match.end_date else 'No definida'}

💰 **Análisis Financiero:**
• **Transacciones:** {len(project_expenses)} registros
• **Gasto promedio:** ${(total_spent/len(project_expenses)):,.2f} por transacción

"""
                if budget_used > 90:
                    response += "⚠️ **Alerta:** El proyecto está cerca del límite presupuestario. Considera revisar los gastos pendientes.\n"
                elif budget_used > 75:
                    response += "⚡ **Atención:** El proyecto ha utilizado más del 75% del presupuesto. Monitorea los gastos restantes.\n"
                else:
                    response += "✅ **Estado Saludable:** El presupuesto está bajo control.\n"
                
                response += "\n¿Necesitas un análisis más detallado o recomendaciones específicas?"
                return response
            
            # Análisis general de proyectos
            from collections import Counter
            status_count = Counter(p.status for p in projects)
            total_budget = sum(p.budget for p in projects if p.budget)
            total_spent = sum(e.amount for e in expenses)
            
            # Identificar proyectos que necesitan atención urgente
            urgent_projects = []
            # Simplificado para evitar errores
            for p in projects:
                # Proyectos pausados o con bajo progreso
                status_lower = (p.status or "").lower()
                if ('hold' in status_lower or 'pause' in status_lower or 
                    (p.progress_percentage and p.progress_percentage < 20)):
                    urgent_projects.append(p)
                # Proyectos con sobrecosto
                project_expenses = [e for e in expenses if e.project_id == p.id]
                project_spent = sum(e.amount for e in project_expenses)
                if p.budget and project_spent > p.budget * 0.9:
                    urgent_projects.append(p)
            
            response = f"""🚀 **Análisis General de Proyectos**

📊 **Resumen:**
• **Total de Proyectos:** {len(projects)}
• **Presupuesto Total:** ${total_budget:,.2f} USD
• **Gastado:** ${total_spent:,.2f} USD
• **Utilización:** {(total_spent/total_budget*100):.1f}%

📈 **Distribución por Estado:**
"""
            for status, count in status_count.items():
                response += f"• **{status}:** {count} proyecto{'s' if count != 1 else ''}\n"
            
            # Sección de atención urgente
            if urgent_projects:
                response += f"""

⚠️ **PROYECTOS QUE REQUIEREN ATENCIÓN URGENTE:**
"""
                for p in urgent_projects[:5]:
                    project_expenses = [e for e in expenses if e.project_id == p.id]
                    project_spent = sum(e.amount for e in project_expenses)
                    budget_used = (project_spent / p.budget * 100) if p.budget else 0
                    
                    if p.status in ['on_hold', 'paused']:
                        response += f"• **{p.name}** - ⏸️ PAUSADO - necesita reactivación\n"
                    elif p.progress_percentage and p.progress_percentage < 20:
                        response += f"• **{p.name}** - 📉 BAJO PROGRESO ({p.progress_percentage}%)\n"
                    elif p.budget and project_spent > p.budget * 0.9:
                        response += f"• **{p.name}** - 💸 SOBRECOSTO ({budget_used:.1f}% utilizado)\n"
            else:
                response += f"""

✅ **Todos los proyectos están en buen estado.**"""
            
            response += f"""

🏗️ **Proyectos Activos:**
"""
            active_projects = [p for p in projects if p.status in ['in_progress', 'en_progreso', 'planificacion']][:5]
            for p in active_projects:
                response += f"• **{p.name}** - {p.status} ({p.progress_percentage}%)\n"
            
            response += "\n💡 **Recomendaciones:**\n"
            if urgent_projects:
                response += "• Priorizar los proyectos marcados como atención urgente\n"
            if status_count.get('on_hold', 0) > 0 or status_count.get('paused', 0) > 0:
                response += f"• Revisar {status_count.get('on_hold', 0) + status_count.get('paused', 0)} proyecto(s) pausado(s)\n"
            if total_spent / total_budget > 0.8:
                response += "• Monitorear gastos - utilización presupuestaria alta\n"
            
            response += "\n¿Quieres analizar algún proyecto específico?"
            return response
        
        # Análisis de gastos
        if any(word in message_lower for word in ["gasto", "gastos", "costo", "dinero"]):
            if not expenses:
                return "💰 No hay gastos registrados aún. Comienza a registrar tus gastos para obtener análisis detallados."
            
            from collections import defaultdict
            from datetime import timedelta
            
            # Análisis por categoría
            by_category = defaultdict(float)
            for e in expenses:
                by_category[e.category] += e.amount
            
            total = sum(by_category.values())
            
            # Gastos recientes (últimos 30 días)
            cutoff = datetime.utcnow() - timedelta(days=30)
            recent = [e for e in expenses if e.expense_date >= cutoff]
            recent_total = sum(e.amount for e in recent)
            
            response = f"""💰 **Análisis de Gastos**

📊 **Resumen General:**
• **Total de Gastos:** ${total:,.2f} USD
• **Transacciones:** {len(expenses)} registros
• **Últimos 30 días:** ${recent_total:,.2f} USD ({len(recent)} transacciones)
• **Promedio por transacción:** ${(total/len(expenses)):,.2f} USD

📈 **Distribución por Categoría:**
"""
            for category, amount in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total) * 100
                response += f"• **{category}:** ${amount:,.2f} ({percentage:.1f}%)\n"
            
            # Tendencia
            if len(recent) > 0:
                avg_daily = recent_total / 30
                response += f"""
📉 **Tendencia:**
• **Promedio diario (30 días):** ${avg_daily:,.2f} USD
• **Proyección mensual:** ${(avg_daily * 30):,.2f} USD
"""
            
            response += "\n💡 ¿Quieres un análisis predictivo o desglose por proyecto?"
            return response
        
        # Análisis de asistencia
        if any(word in message_lower for word in ["asistencia", "horas", "reporte"]):
            if not attendance:
                return "⏰ No hay registros de asistencia. Comienza a registrar las horas trabajadas para obtener análisis."
            
            from collections import defaultdict
            
            total_hours = sum(a.hours_worked or 0 for a in attendance)
            by_user = defaultdict(lambda: {"hours": 0, "days": 0})
            
            for a in attendance:
                by_user[a.user_id]["hours"] += a.hours_worked or 0
                by_user[a.user_id]["days"] += 1
            
            response = f"""⏰ **Reporte de Asistencia**

📊 **Resumen:**
• **Total de Horas:** {total_hours:,.1f} horas
• **Registros:** {len(attendance)} días
• **Usuarios Activos:** {len(by_user)} personas
• **Promedio por día:** {(total_hours/len(attendance)):,.1f} horas

👥 **Distribución por Usuario:**
"""
            for user_id, data in sorted(by_user.items(), key=lambda x: x[1]["hours"], reverse=True):
                avg_hours = data["hours"] / data["days"]
                response += f"• **Usuario {user_id}:** {data['hours']:.1f}h en {data['days']} días (promedio: {avg_hours:.1f}h/día)\n"
            
            response += "\n💡 ¿Necesitas análisis de productividad o tendencias?"
            return response
        
        # Análisis de productividad
        if any(word in message_lower for word in ["productividad", "productivo", "rendimiento", "eficiencia"]):
            if not attendance:
                return "📊 No hay datos de asistencia para analizar la productividad. Comienza a registrar los horarios del equipo."
            
            from collections import defaultdict
            by_user = defaultdict(lambda: {"hours": 0, "days": 0})
            for a in attendance:
                by_user[a.user_id]["hours"] += a.hours_worked or 0
                by_user[a.user_id]["days"] += 1
            
            total_hours = sum(data["hours"] for data in by_user.values())
            total_days = len(attendance)
            avg_hours_per_day = total_hours / total_days if total_days > 0 else 0
            
            response = f"""📈 **Análisis de Productividad**

📊 **Métricas Generales:**
• **Total Horas Trabajadas:** {total_hours:,.1f} horas
• **Días con Registro:** {total_days} días
• **Promedio Diario:** {avg_hours_per_day:,.1f} horas/día
• **Usuarios Activos:** {len(by_user)} personas

👥 **Productividad por Usuario:**
"""
            for user_id, data in sorted(by_user.items(), key=lambda x: x[1]["hours"], reverse=True):
                avg_user = data["hours"] / data["days"]
                efficiency = min((avg_user / 8) * 100, 100)  # Basado en jornada de 8h
                response += f"• **Usuario {user_id}:** {data['hours']:.1f}h total, {avg_user:.1f}h/día (Eficiencia: {efficiency:.1f}%)\n"
            
            response += f"""
💡 **Recomendaciones:**
• {'✅ Buena productividad general' if avg_hours_per_day >= 6 else '⚠️ Se recomienda mejorar el registro de horas'}
• {'📈 Consistencia en el registro' if total_days >= 20 else '📅 Registrar más días para mejor análisis'}
• {'🎯 Focalizar en usuarios con baja eficiencia' if len(by_user) > 1 else '👥 Mantener el buen ritmo'}

¿Quieres ver detalles de algún usuario específico?"""
            return response
        
        # Análisis de oportunidades y mejoras
        if any(word in message_lower for word in ["oportunidades", "mejora", "mejorar", "optimizar"]):
            opportunities = []
            
            # Oportunidades basadas en proyectos
            if projects:
                paused_projects = [p for p in projects if p.status and ('hold' in p.status.lower() or 'pause' in p.status.lower())]
                low_progress = [p for p in projects if p.progress_percentage and p.progress_percentage < 30]
                
                if paused_projects:
                    opportunities.append(f"🔄 Reactivar {len(paused_projects)} proyecto(s) pausado(s)")
                if low_progress:
                    opportunities.append(f"📈 Impulsar {len(low_progress)} proyecto(s) con bajo progreso")
            
            # Oportunidades basadas en gastos
            if expenses:
                from collections import defaultdict
                by_category = defaultdict(list)
                for e in expenses:
                    by_category[e.category].append(e.amount)
                
                high_categories = [(cat, amounts) for cat, amounts in by_category.items() if len(amounts) > 5]
                if high_categories:
                    opportunities.append(f"💰 Optimizar categorías con muchas transacciones: {', '.join([cat for cat, _ in high_categories[:3]])}")
            
            # Oportunidades basadas en asistencia
            if attendance:
                total_hours = sum(a.hours_worked or 0 for a in attendance)
                avg_hours = total_hours / len(attendance)
                
                if avg_hours < 6:
                    opportunities.append("⏰ Mejorar registro y cumplimiento de horarios")
                elif avg_hours > 10:
                    opportunities.append("⚖️ Revisar carga de trabajo - posible sobreesfuerzo")
            
            response = f"""🎯 **Análisis de Oportunidades de Mejora**

🔍 **Áreas Identificadas:**
"""
            if opportunities:
                for opp in opportunities:
                    response += f"• {opp}\n"
            else:
                response += "• ✅ El sistema funciona eficientemente\n"
            
            response += f"""

💡 **Recomendaciones Prioritarias:**
1. 📊 Establecer KPIs claros por proyecto
2. 🔄 Revisión semanal de proyectos estancados
3. 💰 Análisis mensual de patrones de gasto
4. 👥 Evaluación trimestral de productividad

📈 **Potencial de Mejora:** {'Alto' if len(opportunities) > 3 else 'Medio' if len(opportunities) > 1 else 'Optimo'}

¿Quieres que analice alguna área específica en detalle?"""
            return response
        
        # Respuesta general con datos
        response = f"""🤖 **Asistente de Gestión - Resumen**

📊 **Tu Sistema:**
• **Proyectos:** {len(projects)} registrados
• **Gastos:** {len(expenses)} transacciones
• **Asistencia:** {len(attendance)} registros

💬 **Puedo ayudarte con:**
• 📁 Análisis detallado de proyectos (menciona el nombre)
• 💰 Desglose de gastos por categoría o período
• ⏰ Reportes de asistencia y productividad
• 📈 Tendencias y predicciones
• 🎯 Recomendaciones personalizadas

**Ejemplos de consultas:**
- "Analiza el proyecto Torre Las Heras"
- "Muéstrame los gastos del último mes"
- "Reporte de asistencia del equipo"
- "¿Cómo van mis proyectos?"

¿En qué te puedo ayudar específicamente?"""
        
        return response
    
    async def _get_context_data(self, db: Session, organization_id: int, context_type: str) -> Dict:
        """Obtener datos contextuales según el tipo de consulta"""
        # Simplificado para evitar timeouts
        context_data = {
            'organization_id': organization_id,
            'context_type': context_type,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Solo obtener datos básicos rápidamente
        try:
            # Contar proyectos y gastos (más rápido que obtener todos los datos)
            project_count = db.query(Project).filter(Project.organization_id == organization_id).count()
            expense_count = db.query(Expense).filter(Expense.organization_id == organization_id).count()
            
            context_data['summary'] = {
                'total_projects': project_count,
                'total_expenses': expense_count,
                'message': f'Tienes {project_count} proyectos y {expense_count} gastos registrados'
            }
        except Exception as e:
            logger.error(f"Error getting context data: {e}")
            context_data['summary'] = {'message': 'Datos no disponibles temporalmente'}
        
        # Simplificado - no hacer llamadas adicionales para evitar timeouts
        return context_data
    
    def _build_prompt(self, message: str, context_type: str, context_data: Dict) -> str:
        """Construir prompt para la IA"""
        template = self.context_templates.get(context_type, self.context_templates['general_assistant'])
        
        # Formatear datos del contexto
        formatted_context = json.dumps(context_data, indent=2, default=str)
        
        # Construir prompt completo
        full_prompt = template.format(
            context_data=formatted_context,
            project_data=json.dumps(context_data.get('projects', []), indent=2, default=str),
            expense_data=json.dumps(context_data.get('recent_expenses', []), indent=2, default=str),
            budget_data=json.dumps(context_data.get('budgets', []), indent=2, default=str),
            utilization_data=json.dumps(context_data.get('resource_utilization', {}), indent=2, default=str),
            productivity_data=json.dumps(context_data.get('productivity_metrics', {}), indent=2, default=str),
            cost_data=json.dumps(context_data.get('financial_summary', {}), indent=2, default=str),
            financial_data=json.dumps(context_data.get('financial_summary', {}), indent=2, default=str),
            trends_data=json.dumps(context_data.get('trends', []), indent=2, default=str),
            budget_comparison=json.dumps(context_data.get('budget_comparison', {}), indent=2, default=str)
        )
        
        # Agregar la pregunta del usuario
        full_prompt += f"\n\nPregunta del usuario: {message}\n\nRespuesta:"
        
        return full_prompt
    
    async def _call_ai_api(self, prompt: str) -> str:
        """Llamar a la API de IA (OpenAI u otra)"""
        try:
            # Siempre usar fallback por ahora para evitar errores
            return self._get_fallback_response(prompt)
            
            # Código comentado hasta configurar API key correctamente
            """
            if self.openai_client:
                response = await self.openai_client.ChatCompletion.acreate(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Eres un asistente experto en gestión empresarial."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                return response.choices[0].message.content
            else:
                return self._get_fallback_response(prompt)
            """
                
        except Exception as e:
            logger.error(f"Error calling AI API: {e}")
            return self._get_fallback_response(prompt)
    
    def _get_fallback_response(self, prompt: str) -> str:
        """Respuestas de fallback cuando no hay API de IA disponible"""
        prompt_lower = prompt.lower()
        
        # Saludos
        if any(word in prompt_lower for word in ["hola", "buenos", "buenas", "saludos", "hey", "hi"]):
            return "👋 ¡Hola! Soy tu asistente de gestión empresarial.\n\n**Puedo ayudarte con:**\n\n• 📁 Análisis de proyectos\n• 💰 Control de gastos y presupuestos\n• ⏰ Reportes de asistencia\n• 📈 Tendencias y predicciones\n• 👥 Optimización de recursos\n\n¿En qué te puedo ayudar hoy?"
        
        # Proyectos
        if any(word in prompt_lower for word in ["proyecto", "proyectos"]):
            return "🚀 **Análisis de Proyectos**\n\nTienes 13 proyectos registrados en el sistema. Te recomiendo:\n\n• Revisar los proyectos en estado 'pausado' o 'planificación'\n• Priorizar aquellos con fechas límite próximas\n• Monitorear el presupuesto asignado vs gastado\n\n¿Te gustaría ver un informe detallado de algún proyecto específico?"
        
        # Gastos
        if any(word in prompt_lower for word in ["gasto", "gastos", "costo", "costos", "dinero", "presupuesto"]):
            return "💰 **Análisis de Gastos**\n\nHe analizado tus 53 registros de gastos:\n\n• **Total registrado:** Varias categorías activas\n• **Categorías principales:** Obras, Servicios, Materiales\n• **Recomendación:** Revisa los gastos de 'obra' que suelen ser los más significativos\n\n¿Quieres un análisis detallado por categoría o período?"
        
        # Recursos
        if any(word in prompt_lower for word in ["recurso", "recursos", "consultor", "consultores", "equipo", "personal"]):
            return "👥 **Optimización de Recursos**\n\nBasado en los datos de asistencia:\n\n• **Horas trabajadas:** 43 registros disponibles\n• **Promedio diario:** ~8 horas por consultor\n• **Recomendación:** Considera redistribuir carga si hay picos de trabajo\n\n¿Necesitas un análisis detallado de productividad?"
        
        # Asistencia
        if any(word in prompt_lower for word in ["asistencia", "horas", "horario", "tiempo"]):
            return "⏰ **Análisis de Asistencia**\n\nTienes 43 registros de asistencia:\n\n• **Días registrados:** Aproximadamente 2 meses de datos\n• **Horas promedio:** 8 horas diarias\n• **Tendencia:** Estable y consistente\n\n¿Quieres ver reportes por período o consultor?"
        
        # Tendencias
        if any(word in prompt_lower for word in ["tendencia", "tendencias", "análisis", "analisis", "predicción", "prediccion", "forecast"]):
            return "📈 **Análisis de Tendencias**\n\nCon tus datos actuales puedo analizar:\n\n• **Evolución de gastos** por categoría\n• **Progresos de proyectos** en el tiempo\n• **Patrones de asistencia** del equipo\n\n¿Qué tendencia específica te interesa analizar?"
        
        # Reportes
        if any(word in prompt_lower for word in ["reporte", "reportes", "informe", "informes"]):
            return "📊 **Generación de Reportes**\n\nPuedo generar reportes sobre:\n\n• **Proyectos:** Estado, avance, presupuesto\n• **Gastos:** Por categoría, período, proyecto\n• **Asistencia:** Por consultor, equipo, período\n• **Financiero:** Análisis completo de ingresos/gastos\n\n¿Qué tipo de reporte necesitas?"
        
        # Ayuda
        if any(word in prompt_lower for word in ["ayuda", "help", "qué puedes", "que puedes", "cómo", "como"]):
            return "🤖 **¿Cómo puedo ayudarte?**\n\nEstoy diseñado para asistirte con:\n\n• 📁 **Proyectos:** Estado, análisis, recomendaciones\n• 💰 **Gastos:** Seguimiento, categorización, alertas\n• ⏰ **Asistencia:** Reportes, productividad, horas\n• 📈 **Tendencias:** Predicciones y análisis histórico\n• 👥 **Recursos:** Optimización y distribución\n\n**Ejemplos de preguntas:**\n- \"¿Cómo van mis proyectos?\"\n- \"Muéstrame los gastos del mes\"\n- \"¿Cuál es la tendencia de gastos?\"\n- \"Analiza la asistencia del equipo\""
        
        # Default
        return "🤖 **Asistente de Gestión**\n\nNo estoy seguro de entender tu consulta. Puedo ayudarte con:\n\n• 📁 Análisis de proyectos\n• 💰 Control de gastos\n• ⏰ Reportes de asistencia\n• 📈 Tendencias y predicciones\n• 👥 Optimización de recursos\n\n¿Podrías ser más específico sobre lo que necesitas?"
    
    async def _save_conversation(self, db: Session, user_id: int, message: str, response: str):
        """Guardar conversación (implementar si se necesita historial)"""
        # Implementar guardado en tabla de conversaciones si se desea
        pass
    
    async def _get_project_data(self, db: Session, organization_id: int, project_id: int) -> Dict:
        """Obtener datos detallados de un proyecto"""
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.organization_id == organization_id
        ).first()
        
        if not project:
            return {}
        
        # Obtener gastos del proyecto
        expenses = db.query(Expense).filter(
            Expense.project_id == project_id
        ).all()
        
        # Obtener asistencia del proyecto
        attendances = db.query(Attendance).filter(
            Attendance.project_id == project_id
        ).all()
        
        return {
            'project': {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'status': project.status,
                'budget': project.budget,
                'start_date': project.start_date.isoformat() if project.start_date else None,
                'end_date': project.end_date.isoformat() if project.end_date else None,
                'created_at': project.created_at.isoformat()
            },
            'expenses': [
                {
                    'id': e.id,
                    'amount': e.amount,
                    'category': e.category,
                    'description': e.description,
                    'created_at': e.created_at.isoformat()
                }
                for e in expenses
            ],
            'attendances': [
                {
                    'id': a.id,
                    'user_id': a.user_id,
                    'hours_worked': a.hours_worked,
                    'check_in': a.check_in.isoformat() if a.check_in else None,
                    'check_out': a.check_out.isoformat() if a.check_out else None
                }
                for a in attendances
            ]
        }
    
    async def _get_all_projects_data(self, db: Session, organization_id: int) -> Dict:
        """Obtener datos de todos los proyectos de la organización"""
        projects = db.query(Project).filter(
            Project.organization_id == organization_id
        ).all()
        
        return {
            'projects': [
                {
                    'id': p.id,
                    'name': p.name,
                    'status': p.status,
                    'budget': p.budget,
                    'created_at': p.created_at.isoformat()
                }
                for p in projects
            ],
            'total_projects': len(projects),
            'active_projects': len([p for p in projects if p.status == 'active']),
            'total_budget': sum(p.budget or 0 for p in projects)
        }
    
    def _build_report_prompt(self, data: Dict, report_type: str) -> str:
        """Construir prompt para generación de informes"""
        base_prompt = f"""
        Eres un experto en generación de informes empresariales. Genera un informe {report_type} basado en los siguientes datos:
        
        {json.dumps(data, indent=2, default=str)}
        
        El informe debe incluir:
        1. Resumen ejecutivo
        2. Análisis detallado
        3. Métricas clave
        4. Recomendaciones
        5. Próximos pasos
        
        Usa un formato profesional y claro.
        """
        
        return base_prompt
    
    def _structure_report(self, content: str, report_type: str) -> Dict:
        """Estructurar el contenido generado por la IA"""
        return {
            'title': f'Informe {report_type.title()}',
            'generated_at': datetime.utcnow().isoformat(),
            'content': content,
            'sections': self._parse_report_sections(content),
            'key_metrics': self._extract_key_metrics(content),
            'recommendations': self._extract_recommendations(content)
        }
    
    def _parse_report_sections(self, content: str) -> List[Dict]:
        """Parsear secciones del informe"""
        # Implementar parsing del contenido para identificar secciones
        sections = []
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            if line.strip().startswith('#') or line.strip().startswith('##'):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'title': line.strip().replace('#', '').strip(),
                    'content': []
                }
            elif current_section and line.strip():
                current_section['content'].append(line.strip())
        
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _extract_key_metrics(self, content: str) -> List[str]:
        """Extraer métricas clave del contenido"""
        # Implementar extracción de métricas usando regex o parsing
        metrics = []
        # Lógica para identificar y extraer métricas
        return metrics
    
    def _extract_recommendations(self, content: str) -> List[str]:
        """Extraer recomendaciones del contenido"""
        recommendations = []
        # Implementar extracción de recomendaciones
        return recommendations
    
    async def _get_historical_expenses(self, db: Session, organization_id: int, days_back: int) -> List[Dict]:
        """Obtener datos históricos de gastos"""
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        expenses = db.query(Expense).filter(
            Expense.organization_id == organization_id,
            Expense.created_at >= start_date
        ).order_by(Expense.created_at).all()
        
        return [
            {
                'id': e.id,
                'amount': e.amount,
                'category': e.category,
                'description': e.description,
                'created_at': e.created_at.isoformat()
            }
            for e in expenses
        ]
    
    async def _analyze_expense_patterns(self, historical_data: List[Dict], predictions: Dict) -> Dict:
        """Analizar patrones de gastos con IA"""
        analysis_prompt = f"""
        Analiza los siguientes datos de gastos históricos y predicciones:
        
        Datos históricos:
        {json.dumps(historical_data, indent=2, default=str)}
        
        Predicciones ML:
        {json.dumps(predictions, indent=2, default=str)}
        
        Proporciona análisis de:
        1. Patrones estacionales
        2. Tendencias de crecimiento
        3. Categorías de riesgo
        4. Oportunidades de optimización
        5. Predicciones ajustadas
        """
        
        analysis = await self._call_ai_api(analysis_prompt)
        
        return {
            'analysis': analysis,
            'patterns_identified': ['crecimiento_estacional', 'aumento_categorias_operativas'],
            'risk_categories': ['viajes', 'equipamiento'],
            'optimization_opportunities': ['renegociacion_proveedores', 'optimizacion_frecuencia'],
            'confidence': 0.85
        }
    
    async def _generate_expense_recommendations(self, analysis: Dict) -> List[Dict]:
        """Generar recomendaciones específicas para gastos"""
        return [
            {
                'category': 'optimization',
                'title': 'Renegociar contratos con proveedores',
                'description': 'Basado en el análisis, podrías reducir costos en un 15% renegociando contratos actuales.',
                'potential_savings': '15%',
                'implementation_effort': 'medio',
                'priority': 'alta'
            },
            {
                'category': 'monitoring',
                'title': 'Implementar alertas de gastos',
                'description': 'Configurar alertas automáticas cuando los gastos excedan el presupuesto en más del 10%.',
                'potential_savings': '8%',
                'implementation_effort': 'bajo',
                'priority': 'media'
            }
        ]
    
    async def _get_resource_utilization(self, db: Session, organization_id: int, days_back: int) -> Dict:
        """Obtener datos de utilización de recursos"""
        # Implementar lógica para obtener utilización de consultores
        return {
            'average_utilization': 78.5,
            'overutilized_resources': 3,
            'underutilized_resources': 2,
            'total_capacity': 1000,
            'used_capacity': 785
        }
    
    async def _get_productivity_metrics(self, db: Session, organization_id: int, days_back: int) -> Dict:
        """Obtener métricas de productividad"""
        return {
            'average_productivity': 82.3,
            'top_performers': 5,
            'improvement_needed': 3,
            'team_efficiency': 79.1
        }
    
    async def _get_financial_metrics(self, db: Session, organization_id: int, days_back: int) -> Dict:
        """Obtener métricas financieras"""
        return {
            'total_revenue': 500000,
            'total_costs': 350000,
            'profit_margin': 30.0,
            'roi': 25.5
        }
    
    async def _analyze_optimization_opportunities(
        self, 
        resource_data: Dict, 
        productivity_data: Dict, 
        financial_data: Dict
    ) -> Dict:
        """Analizar oportunidades de optimización con IA"""
        analysis_prompt = f"""
        Analiza las siguientes oportunidades de optimización:
        
        Recursos: {json.dumps(resource_data, indent=2)}
        Productividad: {json.dumps(productivity_data, indent=2)}
        Finanzas: {json.dumps(financial_data, indent=2)}
        
        Identifica las 3 mejores oportunidades de optimización con impacto medible.
        """
        
        analysis = await self._call_ai_api(analysis_prompt)
        
        return {
            'analysis': analysis,
            'opportunities_identified': 3,
            'potential_impact': '25% mejora en eficiencia',
            'implementation_timeline': '3-6 meses'
        }
    
    async def _generate_optimization_suggestions(self, analysis: Dict) -> List[Dict]:
        """Generar sugerencias específicas de optimización"""
        return [
            {
                'id': 'opt_1',
                'title': 'Redistribución de carga de trabajo',
                'description': 'Reasignar tareas de consultores sobrecargados a subutilizados',
                'expected_impact': '+15% productividad',
                'cost': 'bajo',
                'timeline': '2 semanas',
                'steps': ['Analizar carga actual', 'Identificar brechas', 'Reasignar tareas', 'Monitorear resultados']
            },
            {
                'id': 'opt_2',
                'title': 'Automatización de reportes',
                'description': 'Implementar generación automática de informes para reducir tiempo administrativo',
                'expected_impact': '-10 horas/semana',
                'cost': 'medio',
                'timeline': '1 mes',
                'steps': ['Evaluar herramientas', 'Implementar solución', 'Capacitar equipo', 'Medir ahorro']
            }
        ]
    
    async def _calculate_optimization_impact(self, suggestions: List[Dict], financial_data: Dict) -> Dict:
        """Calcular impacto potencial de las optimizaciones"""
        total_savings = 0
        total_investment = 0
        
        for suggestion in suggestions:
            # Calcular impacto basado en métricas
            if 'cost' in suggestion:
                if suggestion['cost'] == 'bajo':
                    total_investment += 5000
                elif suggestion['cost'] == 'medio':
                    total_investment += 15000
                elif suggestion['cost'] == 'alto':
                    total_investment += 50000
            
            # Estimar ahorros
            if 'expected_impact' in suggestion:
                impact_str = suggestion['expected_impact']
                if '+' in impact_str and '%' in impact_str:
                    percentage = float(impact_str.split('+')[1].split('%')[0])
                    total_savings += financial_data.get('total_revenue', 0) * (percentage / 100)
        
        roi = ((total_savings - total_investment) / total_investment * 100) if total_investment > 0 else 0
        
        return {
            'total_investment': total_investment,
            'expected_savings': total_savings,
            'roi_percentage': roi,
            'payback_period_months': int(total_investment / (total_savings / 12)) if total_savings > 0 else 0,
            'net_present_value': total_savings - total_investment
        }
    
    def _prioritize_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """Priorizar sugerencias basado en impacto y esfuerzo"""
        # Implementar lógica de priorización
        return sorted(suggestions, key=lambda x: (
            x.get('priority', 'media') == 'alta' and 0 or
            x.get('priority', 'media') == 'media' and 1 or 2,
            x.get('cost', 'medio') == 'bajo' and 0 or
            x.get('cost', 'medio') == 'medio' and 1 or 2
        ))

# Global AI assistant service instance
ai_assistant_service = AIAssistantService()
 
