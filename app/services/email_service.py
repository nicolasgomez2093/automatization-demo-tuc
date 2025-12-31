import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import csv
import io
from jinja2 import Template
from sqlalchemy.orm import Session
from app.models.expense import Expense
from app.models.attendance import Attendance
from app.models.user import User
from app.models.project import Project

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict]] = None
    ) -> bool:
        """Send email with optional attachments"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Attach files if provided
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)

            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()

            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def generate_weekly_report(self, db: Session, organization_id: int) -> Dict:
        """Generate weekly report data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        # Get expenses data
        expenses = db.query(Expense).filter(
            Expense.organization_id == organization_id,
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).all()

        # Get attendance data
        attendances = db.query(Attendance).filter(
            Attendance.organization_id == organization_id,
            Attendance.check_in >= start_date,
            Attendance.check_in <= end_date
        ).all()

        # Calculate statistics
        total_expenses = sum(exp.amount for exp in expenses)
        expenses_by_category = {}
        for exp in expenses:
            category = exp.category or 'sin_categorizar'
            expenses_by_category[category] = expenses_by_category.get(category, 0) + exp.amount

        # Calculate hours worked
        total_hours = sum(att.hours_worked or 0 for att in attendances)
        unique_users = len(set(att.user_id for att in attendances))

        # Top expenses
        top_expenses = sorted(expenses, key=lambda x: x.amount, reverse=True)[:5]

        return {
            'period': f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}",
            'total_expenses': total_expenses,
            'expenses_count': len(expenses),
            'expenses_by_category': expenses_by_category,
            'total_hours': total_hours,
            'unique_users': unique_users,
            'attendances_count': len(attendances),
            'top_expenses': [
                {
                    'description': exp.description,
                    'amount': exp.amount,
                    'category': exp.category,
                    'date': exp.created_at.strftime('%d/%m/%Y')
                }
                for exp in top_expenses
            ]
        }

    def generate_monthly_report(self, db: Session, organization_id: int) -> Dict:
        """Generate monthly report data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # Get expenses data
        expenses = db.query(Expense).filter(
            Expense.organization_id == organization_id,
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).all()

        # Get attendance data
        attendances = db.query(Attendance).filter(
            Attendance.organization_id == organization_id,
            Attendance.check_in >= start_date,
            Attendance.check_in <= end_date
        ).all()

        # Get projects data
        projects = db.query(Project).filter(
            Project.organization_id == organization_id
        ).all()

        # Calculate statistics
        total_expenses = sum(exp.amount for exp in expenses)
        expenses_by_category = {}
        for exp in expenses:
            category = exp.category or 'sin_categorizar'
            expenses_by_category[category] = expenses_by_category.get(category, 0) + exp.amount

        # Calculate hours worked
        total_hours = sum(att.hours_worked or 0 for att in attendances)
        unique_users = len(set(att.user_id for att in attendances))

        # Project statistics
        project_stats = []
        for project in projects:
            project_expenses = [exp for exp in expenses if exp.project_id == project.id]
            project_total = sum(exp.amount for exp in project_expenses)
            project_stats.append({
                'name': project.name,
                'total_expenses': project_total,
                'expenses_count': len(project_expenses)
            })

        return {
            'period': f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}",
            'total_expenses': total_expenses,
            'expenses_count': len(expenses),
            'expenses_by_category': expenses_by_category,
            'total_hours': total_hours,
            'unique_users': unique_users,
            'attendances_count': len(attendances),
            'active_projects': len(projects),
            'project_stats': sorted(project_stats, key=lambda x: x['total_expenses'], reverse=True)[:10]
        }

    def generate_csv_report(self, data: Dict, report_type: str) -> bytes:
        """Generate CSV report from data"""
        output = io.StringIO()
        
        if report_type == "weekly":
            writer = csv.writer(output)
            writer.writerow(['Reporte Semanal de Actividad'])
            writer.writerow(['Período', data['period']])
            writer.writerow([])
            
            writer.writerow(['Resumen de Gastos'])
            writer.writerow(['Total Gastos', f"${data['total_expenses']:.2f}"])
            writer.writerow(['Cantidad de Gastos', data['expenses_count']])
            writer.writerow([])
            
            writer.writerow(['Gastos por Categoría'])
            for category, amount in data['expenses_by_category'].items():
                writer.writerow([category, f"${amount:.2f}"])
            writer.writerow([])
            
            writer.writerow(['Top 5 Gastos'])
            writer.writerow(['Descripción', 'Monto', 'Categoría', 'Fecha'])
            for expense in data['top_expenses']:
                writer.writerow([
                    expense['description'],
                    f"${expense['amount']:.2f}",
                    expense['category'],
                    expense['date']
                ])
            writer.writerow([])
            
            writer.writerow(['Resumen de Asistencia'])
            writer.writerow(['Total Horas', f"{data['total_hours']:.2f}"])
            writer.writerow(['Usuarios Activos', data['unique_users']])
            writer.writerow(['Registros', data['attendances_count']])
            
        elif report_type == "monthly":
            writer = csv.writer(output)
            writer.writerow(['Reporte Mensual de Actividad'])
            writer.writerow(['Período', data['period']])
            writer.writerow([])
            
            writer.writerow(['Resumen General'])
            writer.writerow(['Total Gastos', f"${data['total_expenses']:.2f}"])
            writer.writerow(['Cantidad de Gastos', data['expenses_count']])
            writer.writerow(['Total Horas Trabajadas', f"{data['total_hours']:.2f}"])
            writer.writerow(['Usuarios Activos', data['unique_users']])
            writer.writerow(['Proyectos Activos', data['active_projects']])
            writer.writerow([])
            
            writer.writerow(['Gastos por Categoría'])
            for category, amount in data['expenses_by_category'].items():
                writer.writerow([category, f"${amount:.2f}"])
            writer.writerow([])
            
            writer.writerow(['Estadísticas por Proyecto'])
            writer.writerow(['Proyecto', 'Total Gastos', 'Cantidad de Gastos'])
            for project in data['project_stats']:
                writer.writerow([
                    project['name'],
                    f"${project['total_expenses']:.2f}",
                    project['expenses_count']
                ])

        return output.getvalue().encode('utf-8')

    def send_weekly_report(self, db: Session, organization_id: int, to_emails: List[str]) -> bool:
        """Send weekly report email"""
        try:
            # Generate report data
            data = self.generate_weekly_report(db, organization_id)
            
            # Generate HTML email
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Reporte Semanal</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .header { background: #2563eb; color: white; padding: 20px; text-align: center; }
                    .section { margin: 20px 0; padding: 15px; border: 1px solid #e5e7eb; border-radius: 8px; }
                    .stat { display: inline-block; margin: 10px; padding: 10px; background: #f3f4f6; border-radius: 4px; }
                    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
                    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #e5e7eb; }
                    th { background: #f9fafb; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📊 Reporte Semanal de Actividad</h1>
                    <p>{{ period }}</p>
                </div>
                
                <div class="section">
                    <h2>💰 Resumen de Gastos</h2>
                    <div class="stat">Total: ${{ "%.2f"|format(total_expenses) }}</div>
                    <div class="stat">Cantidad: {{ expenses_count }}</div>
                </div>
                
                <div class="section">
                    <h2>⏰ Resumen de Asistencia</h2>
                    <div class="stat">Total Horas: {{ "%.2f"|format(total_hours) }}</div>
                    <div class="stat">Usuarios Activos: {{ unique_users }}</div>
                    <div class="stat">Registros: {{ attendances_count }}</div>
                </div>
                
                <div class="section">
                    <h2>📈 Gastos por Categoría</h2>
                    <table>
                        <tr><th>Categoría</th><th>Monto</th></tr>
                        {% for category, amount in expenses_by_category.items() %}
                        <tr>
                            <td>{{ category }}</td>
                            <td>${{ "%.2f"|format(amount) }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
                
                <div class="section">
                    <h2>🔝 Top 5 Gastos</h2>
                    <table>
                        <tr><th>Descripción</th><th>Monto</th><th>Categoría</th><th>Fecha</th></tr>
                        {% for expense in top_expenses %}
                        <tr>
                            <td>{{ expense.description }}</td>
                            <td>${{ "%.2f"|format(expense.amount) }}</td>
                            <td>{{ expense.category }}</td>
                            <td>{{ expense.date }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </body>
            </html>
            """
            
            template = Template(html_template)
            html_body = template.render(**data)
            
            # Generate CSV attachment
            csv_content = self.generate_csv_report(data, "weekly")
            
            # Send email
            return self.send_email(
                to_emails=to_emails,
                subject=f"📊 Reporte Semanal - {data['period']}",
                html_body=html_body,
                attachments=[{
                    'filename': f"reporte_semanal_{datetime.now().strftime('%Y%m%d')}.csv",
                    'content': csv_content
                }]
            )
        except Exception as e:
            print(f"Error sending weekly report: {e}")
            return False

    def send_monthly_report(self, db: Session, organization_id: int, to_emails: List[str]) -> bool:
        """Send monthly report email"""
        try:
            # Generate report data
            data = self.generate_monthly_report(db, organization_id)
            
            # Generate HTML email
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Reporte Mensual</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .header { background: #dc2626; color: white; padding: 20px; text-align: center; }
                    .section { margin: 20px 0; padding: 15px; border: 1px solid #e5e7eb; border-radius: 8px; }
                    .stat { display: inline-block; margin: 10px; padding: 10px; background: #f3f4f6; border-radius: 4px; }
                    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
                    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #e5e7eb; }
                    th { background: #f9fafb; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📊 Reporte Mensual de Actividad</h1>
                    <p>{{ period }}</p>
                </div>
                
                <div class="section">
                    <h2>📈 Resumen General</h2>
                    <div class="stat">Total Gastos: ${{ "%.2f"|format(total_expenses) }}</div>
                    <div class="stat">Cantidad Gastos: {{ expenses_count }}</div>
                    <div class="stat">Total Horas: {{ "%.2f"|format(total_hours) }}</div>
                    <div class="stat">Usuarios Activos: {{ unique_users }}</div>
                    <div class="stat">Proyectos Activos: {{ active_projects }}</div>
                </div>
                
                <div class="section">
                    <h2>💰 Gastos por Categoría</h2>
                    <table>
                        <tr><th>Categoría</th><th>Monto</th></tr>
                        {% for category, amount in expenses_by_category.items() %}
                        <tr>
                            <td>{{ category }}</td>
                            <td>${{ "%.2f"|format(amount) }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
                
                <div class="section">
                    <h2>🏗️ Estadísticas por Proyecto</h2>
                    <table>
                        <tr><th>Proyecto</th><th>Total Gastos</th><th>Cantidad</th></tr>
                        {% for project in project_stats %}
                        <tr>
                            <td>{{ project.name }}</td>
                            <td>${{ "%.2f"|format(project.total_expenses) }}</td>
                            <td>{{ project.expenses_count }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </body>
            </html>
            """
            
            template = Template(html_template)
            html_body = template.render(**data)
            
            # Generate CSV attachment
            csv_content = self.generate_csv_report(data, "monthly")
            
            # Send email
            return self.send_email(
                to_emails=to_emails,
                subject=f"📊 Reporte Mensual - {data['period']}",
                html_body=html_body,
                attachments=[{
                    'filename': f"reporte_mensual_{datetime.now().strftime('%Y%m%d')}.csv",
                    'content': csv_content
                }]
            )
        except Exception as e:
            print(f"Error sending monthly report: {e}")
            return False

# Global email service instance
email_service = EmailService()
