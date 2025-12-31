import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from app.models.document import (
    Document, DocumentSignature, DocumentApproval, DocumentStatus, DocumentType,
    ConsultantResource, ProjectProfitability, OrganizationKPI, TeamProductivity
)
from app.models.project import Project
from app.models.user import User
from app.models.expense import Expense
from app.models.attendance import Attendance
from app.core.config import settings
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        self.encryption_key = None
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption for secure document storage"""
        try:
            # In production, this should come from a secure key management system
            key_file = os.path.join(settings.UPLOAD_DIR, '.encryption_key')
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    self.encryption_key = f.read()
            else:
                self.encryption_key = Fernet.generate_key()
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                with open(key_file, 'wb') as f:
                    f.write(self.encryption_key)
        except Exception as e:
            logger.error(f"Error initializing encryption: {e}")
            self.encryption_key = None
    
    def upload_document(
        self,
        db: Session,
        organization_id: int,
        title: str,
        description: str,
        document_type: DocumentType,
        file_path: str,
        filename: str,
        file_size: int,
        mime_type: str,
        user_id: int,
        project_id: Optional[int] = None,
        client_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        encrypt_file: bool = False
    ) -> Dict:
        """Upload and store a new document"""
        try:
            # Calculate file checksum
            checksum = self._calculate_file_checksum(file_path)
            
            # Encrypt file if requested
            if encrypt_file and self.encryption_key:
                encrypted_path = self._encrypt_file(file_path)
                is_encrypted = True
                encryption_key_id = "default"
            else:
                encrypted_path = file_path
                is_encrypted = False
                encryption_key_id = None
            
            # Create document record
            document = Document(
                organization_id=organization_id,
                title=title,
                description=description,
                document_type=document_type,
                status=DocumentStatus.DRAFT,
                filename=filename,
                file_path=encrypted_path,
                file_size=file_size,
                mime_type=mime_type,
                checksum=checksum,
                version="1.0",
                is_latest_version=True,
                tags=tags or [],
                is_encrypted=is_encrypted,
                encryption_key_id=encryption_key_id,
                project_id=project_id,
                client_id=client_id,
                user_id=user_id
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            return {
                "success": True,
                "document": {
                    "id": document.id,
                    "title": document.title,
                    "type": document.document_type.value,
                    "status": document.status.value,
                    "version": document.version,
                    "is_encrypted": document.is_encrypted,
                    "created_at": document.created_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def create_document_version(
        self,
        db: Session,
        document_id: int,
        file_path: str,
        filename: str,
        file_size: int,
        user_id: int,
        changelog: Optional[str] = None
    ) -> Dict:
        """Create a new version of an existing document"""
        try:
            # Get original document
            original_doc = db.query(Document).filter(Document.id == document_id).first()
            if not original_doc:
                return {"success": False, "error": "Document not found"}
            
            # Mark original as not latest
            original_doc.is_latest_version = False
            
            # Calculate new version number
            version_parts = original_doc.version.split('.')
            version_parts[-1] = str(int(version_parts[-1]) + 1)
            new_version = ".".join(version_parts)
            
            # Calculate checksum
            checksum = self._calculate_file_checksum(file_path)
            
            # Encrypt if original was encrypted
            if original_doc.is_encrypted and self.encryption_key:
                encrypted_path = self._encrypt_file(file_path)
            else:
                encrypted_path = file_path
            
            # Create new version
            new_doc = Document(
                organization_id=original_doc.organization_id,
                title=original_doc.title,
                description=original_doc.description,
                document_type=original_doc.document_type,
                status=original_doc.status,
                filename=filename,
                file_path=encrypted_path,
                file_size=file_size,
                mime_type=original_doc.mime_type,
                checksum=checksum,
                version=new_version,
                parent_document_id=original_doc.id,
                is_latest_version=True,
                tags=original_doc.tags,
                document_metadata=original_doc.document_metadata,
                is_encrypted=original_doc.is_encrypted,
                encryption_key_id=original_doc.encryption_key_id,
                project_id=original_doc.project_id,
                client_id=original_doc.client_id,
                user_id=user_id
            )
            
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            
            return {
                "success": True,
                "document": {
                    "id": new_doc.id,
                    "version": new_doc.version,
                    "parent_id": new_doc.parent_document_id,
                    "created_at": new_doc.created_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating document version: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def sign_document(
        self,
        db: Session,
        document_id: int,
        user_id: int,
        signature_data: str,
        signature_type: str = "digital",
        ip_address: str = "0.0.0.0",
        user_agent: str = "",
        legal_statement: Optional[str] = None
    ) -> Dict:
        """Add digital signature to document"""
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                return {"success": False, "error": "Document not found"}
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Create verification hash
            verification_data = f"{document_id}_{user_id}_{datetime.utcnow().isoformat()}"
            verification_hash = hashlib.sha256(verification_data.encode()).hexdigest()
            
            # Create signature record
            signature = DocumentSignature(
                document_id=document_id,
                organization_id=document.organization_id,
                user_id=user_id,
                signer_name=user.full_name,
                signer_email=user.email,
                signature_type=signature_type,
                signature_data=signature_data,
                signed_at=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent,
                legal_statement=legal_statement,
                verification_hash=verification_hash
            )
            
            db.add(signature)
            
            # Update document status if all required signatures are collected
            # This would depend on the document's workflow requirements
            document.status = DocumentStatus.APPROVED
            
            db.commit()
            
            return {
                "success": True,
                "signature": {
                    "id": signature.id,
                    "signed_at": signature.signed_at.isoformat(),
                    "verification_hash": signature.verification_hash
                }
            }
            
        except Exception as e:
            logger.error(f"Error signing document: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def create_approval_workflow(
        self,
        db: Session,
        document_id: int,
        approvers: List[Dict],  # List of {user_id, role, requires_signature}
        created_by: int
    ) -> Dict:
        """Create approval workflow for document"""
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                return {"success": False, "error": "Document not found"}
            
            # Update document status
            document.status = DocumentStatus.PENDING_APPROVAL
            
            # Create approval steps
            for i, approver in enumerate(approvers):
                approval = DocumentApproval(
                    document_id=document_id,
                    organization_id=document.organization_id,
                    workflow_step=i + 1,
                    approver_id=approver["user_id"],
                    approver_role=approver["role"],
                    status="pending",
                    requires_signature=approver.get("requires_signature", False),
                    requires_document_review=approver.get("requires_review", True)
                )
                db.add(approval)
            
            db.commit()
            
            return {
                "success": True,
                "workflow_created": True,
                "approval_steps": len(approvers)
            }
            
        except Exception as e:
            logger.error(f"Error creating approval workflow: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def process_approval(
        self,
        db: Session,
        approval_id: int,
        user_id: int,
        approved: bool,
        comments: Optional[str] = None
    ) -> Dict:
        """Process document approval/rejection"""
        try:
            approval = db.query(DocumentApproval).filter(DocumentApproval.id == approval_id).first()
            if not approval:
                return {"success": False, "error": "Approval not found"}
            
            if approval.approver_id != user_id:
                return {"success": False, "error": "Not authorized to approve this document"}
            
            # Update approval
            approval.status = "approved" if approved else "rejected"
            approval.decision_at = datetime.utcnow()
            approval.comments = comments
            
            # Check if all approvals are complete
            document = db.query(Document).filter(Document.id == approval.document_id).first()
            all_approvals = db.query(DocumentApproval).filter(
                DocumentApproval.document_id == approval.document_id
            ).all()
            
            pending_approvals = [a for a in all_approvals if a.status == "pending"]
            rejected_approvals = [a for a in all_approvals if a.status == "rejected"]
            
            if rejected_approvals:
                document.status = DocumentStatus.REJECTED
            elif not pending_approvals:
                document.status = DocumentStatus.APPROVED
            
            db.commit()
            
            return {
                "success": True,
                "status": document.status.value,
                "pending_approvals": len(pending_approvals)
            }
            
        except Exception as e:
            logger.error(f"Error processing approval: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def calculate_consultant_utilization(
        self,
        db: Session,
        organization_id: int,
        consultant_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        """Calculate resource utilization for a consultant"""
        try:
            # Get allocated resources
            allocated = db.query(ConsultantResource).filter(
                ConsultantResource.organization_id == organization_id,
                ConsultantResource.consultant_id == consultant_id,
                ConsultantResource.period_start <= period_end,
                ConsultantResource.period_end >= period_start
            ).all()
            
            total_allocated_hours = sum(r.allocated_hours for r in allocated)
            total_cost = sum(r.cost_per_hour * r.allocated_hours for r in allocated)
            
            # Get actual hours worked from attendance
            attendance = db.query(Attendance).filter(
                Attendance.organization_id == organization_id,
                Attendance.user_id == consultant_id,
                Attendance.check_in >= period_start,
                Attendance.check_out <= period_end,
                Attendance.hours_worked.isnot(None)
            ).all()
            
            actual_hours_worked = sum(a.hours_worked or 0 for a in attendance)
            
            # Get billable hours from projects
            # This would be calculated based on project assignments and time tracking
            billable_hours = actual_hours_worked * 0.8  # Simplified calculation
            
            # Calculate utilization rate
            utilization_rate = (actual_hours_worked / total_allocated_hours * 100) if total_allocated_hours > 0 else 0
            
            # Calculate efficiency score
            efficiency_score = min(100, utilization_rate) if utilization_rate <= 100 else (200 - utilization_rate)
            
            return {
                "success": True,
                "consultant_id": consultant_id,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "allocation": {
                    "total_allocated_hours": total_allocated_hours,
                    "total_cost": total_cost
                },
                "actual": {
                    "hours_worked": actual_hours_worked,
                    "billable_hours": billable_hours,
                    "non_billable_hours": actual_hours_worked - billable_hours
                },
                "metrics": {
                    "utilization_rate": utilization_rate,
                    "efficiency_score": efficiency_score,
                    "billable_percentage": (billable_hours / actual_hours_worked * 100) if actual_hours_worked > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating consultant utilization: {e}")
            return {"success": False, "error": str(e)}
    
    def calculate_project_profitability(
        self,
        db: Session,
        organization_id: int,
        project_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        """Calculate detailed project profitability"""
        try:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.organization_id == organization_id
            ).first()
            
            if not project:
                return {"success": False, "error": "Project not found"}
            
            # Get all expenses for the project
            expenses = db.query(Expense).filter(
                Expense.organization_id == organization_id,
                Expense.project_id == project_id,
                Expense.created_at >= period_start,
                Expense.created_at <= period_end
            ).all()
            
            # Calculate costs by category
            labor_costs = sum(e.amount for e in expenses if e.category in ['salary', 'consultant_fees'])
            material_costs = sum(e.amount for e in expenses if e.category in ['materials', 'equipment'])
            overhead_costs = sum(e.amount for e in expenses if e.category in ['rent', 'utilities', 'admin'])
            other_costs = sum(e.amount for e in expenses if e.category not in ['salary', 'consultant_fees', 'materials', 'equipment', 'rent', 'utilities', 'admin'])
            
            total_costs = labor_costs + material_costs + overhead_costs + other_costs
            
            # Get project revenue (this would come from invoices or contracts)
            # For now, we'll use the project budget as revenue
            total_revenue = project.budget or 0
            
            # Calculate profitability metrics
            gross_profit = total_revenue - total_costs
            gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Net profit (after overhead and other deductions)
            net_profit = gross_profit - (overhead_costs * 0.2)  # Simplified calculation
            net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # ROI calculation
            roi_percentage = (net_profit / total_costs * 100) if total_costs > 0 else 0
            
            # Time tracking
            attendances = db.query(Attendance).filter(
                Attendance.organization_id == organization_id,
                Attendance.project_id == project_id,
                Attendance.check_in >= period_start,
                Attendance.check_out <= period_end
            ).all()
            
            actual_hours = sum(a.hours_worked or 0 for a in attendances)
            estimated_hours = project.estimated_hours or actual_hours
            hours_variance = actual_hours - estimated_hours
            
            # Performance metrics
            schedule_performance = (estimated_hours / actual_hours) if actual_hours > 0 else 0
            cost_performance = (project.budget / total_costs) if total_costs > 0 else 0
            
            # Save profitability record
            profitability = ProjectProfitability(
                organization_id=organization_id,
                project_id=project_id,
                total_budget=project.budget or 0,
                total_costs=total_costs,
                total_revenue=total_revenue,
                gross_profit=gross_profit,
                net_profit=net_profit,
                gross_margin=gross_margin,
                net_margin=net_margin,
                roi_percentage=roi_percentage,
                labor_costs=labor_costs,
                material_costs=material_costs,
                overhead_costs=overhead_costs,
                other_costs=other_costs,
                estimated_hours=estimated_hours,
                actual_hours=actual_hours,
                hours_variance=hours_variance,
                schedule_performance=schedule_performance,
                cost_performance=cost_performance,
                period_start=period_start,
                period_end=period_end
            )
            
            db.add(profitability)
            db.commit()
            
            return {
                "success": True,
                "project_id": project_id,
                "financial_metrics": {
                    "total_budget": project.budget or 0,
                    "total_costs": total_costs,
                    "total_revenue": total_revenue,
                    "gross_profit": gross_profit,
                    "net_profit": net_profit,
                    "gross_margin": gross_margin,
                    "net_margin": net_margin,
                    "roi_percentage": roi_percentage
                },
                "cost_breakdown": {
                    "labor_costs": labor_costs,
                    "material_costs": material_costs,
                    "overhead_costs": overhead_costs,
                    "other_costs": other_costs
                },
                "performance_metrics": {
                    "schedule_performance": schedule_performance,
                    "cost_performance": cost_performance,
                    "hours_variance": hours_variance,
                    "actual_hours": actual_hours,
                    "estimated_hours": estimated_hours
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating project profitability: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def calculate_organization_kpis(
        self,
        db: Session,
        organization_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        """Calculate real-time KPIs for the organization"""
        try:
            kpis = []
            
            # Financial KPIs
            total_revenue = db.query(func.sum(Project.budget)).filter(
                Project.organization_id == organization_id
            ).scalar() or 0
            
            total_expenses = db.query(func.sum(Expense.amount)).filter(
                Expense.organization_id == organization_id,
                Expense.created_at >= period_start,
                Expense.created_at <= period_end
            ).scalar() or 0
            
            profit_margin = ((total_revenue - total_expenses) / total_revenue * 100) if total_revenue > 0 else 0
            
            kpis.append({
                "category": "financial",
                "kpi_name": "Profit Margin",
                "kpi_code": "PROFIT_MARGIN",
                "current_value": profit_margin,
                "target_value": 20.0,
                "unit": "%",
                "status": "good" if profit_margin >= 15 else "warning" if profit_margin >= 10 else "critical"
            })
            
            # Operational KPIs
            total_projects = db.query(Project).filter(
                Project.organization_id == organization_id
            ).count()
            
            active_projects = db.query(Project).filter(
                Project.organization_id == organization_id,
                Project.status == "active"
            ).count()
            
            project_completion_rate = (active_projects / total_projects * 100) if total_projects > 0 else 0
            
            kpis.append({
                "category": "operational",
                "kpi_name": "Project Completion Rate",
                "kpi_code": "PROJECT_COMPLETION",
                "current_value": project_completion_rate,
                "target_value": 85.0,
                "unit": "%",
                "status": "good" if project_completion_rate >= 80 else "warning"
            })
            
            # Productivity KPIs
            total_users = db.query(User).filter(
                User.organization_id == organization_id
            ).count()
            
            total_hours = db.query(func.sum(Attendance.hours_worked)).filter(
                Attendance.organization_id == organization_id,
                Attendance.check_in >= period_start,
                Attendance.check_out <= period_end
            ).scalar() or 0
            
            avg_hours_per_user = total_hours / total_users if total_users > 0 else 0
            
            kpis.append({
                "category": "productivity",
                "kpi_name": "Average Hours per User",
                "kpi_code": "AVG_HOURS_USER",
                "current_value": avg_hours_per_user,
                "target_value": 160.0,
                "unit": "hours",
                "status": "good" if avg_hours_per_user >= 150 else "warning"
            })
            
            # Save KPIs to database
            for kpi in kpis:
                org_kpi = OrganizationKPI(
                    organization_id=organization_id,
                    category=kpi["category"],
                    kpi_name=kpi["kpi_name"],
                    kpi_code=kpi["kpi_code"],
                    current_value=kpi["current_value"],
                    target_value=kpi["target_value"],
                    unit=kpi["unit"],
                    status=kpi["status"],
                    period_start=period_start,
                    period_end=period_end
                )
                db.add(org_kpi)
            
            db.commit()
            
            return {
                "success": True,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "kpis": kpis,
                "summary": {
                    "total_kpis": len(kpis),
                    "critical_count": len([k for k in kpis if k["status"] == "critical"]),
                    "warning_count": len([k for k in kpis if k["status"] == "warning"]),
                    "good_count": len([k for k in kpis if k["status"] == "good"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating organization KPIs: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def calculate_team_productivity(
        self,
        db: Session,
        organization_id: int,
        period_start: datetime,
        period_end: datetime,
        team_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict:
        """Calculate productivity metrics for team or user"""
        try:
            # Get base query for users
            if user_id:
                users = db.query(User).filter(
                    User.id == user_id,
                    User.organization_id == organization_id
                ).all()
            elif team_id:
                # This would filter by team membership when teams are implemented
                users = db.query(User).filter(
                    User.organization_id == organization_id
                ).all()
            else:
                users = db.query(User).filter(
                    User.organization_id == organization_id
                ).all()
            
            productivity_data = []
            
            for user in users:
                # Get attendance data
                attendances = db.query(Attendance).filter(
                    Attendance.user_id == user.id,
                    Attendance.check_in >= period_start,
                    Attendance.check_out <= period_end
                ).all()
                
                hours_worked = sum(a.hours_worked or 0 for a in attendances)
                
                # Get project assignments and tasks
                # This would be enhanced with a proper task management system
                tasks_completed = db.query(Expense).filter(
                    Expense.user_id == user.id,
                    Expense.created_at >= period_start,
                    Expense.created_at <= period_end
                ).count()  # Using expenses as a proxy for tasks
                
                # Calculate productivity metrics
                efficiency_score = min(100, (tasks_completed / max(1, hours_worked / 8)) * 100)
                utilization_rate = (hours_worked / 160) * 100 if hours_worked > 0 else 0  # Assuming 160 hours/month
                
                # Calculate financial contribution
                revenue_generated = tasks_completed * 1000  # Simplified calculation
                cost_incurred = hours_worked * 50  # Simplified hourly rate
                profit_contribution = revenue_generated - cost_incurred
                
                productivity = TeamProductivity(
                    organization_id=organization_id,
                    user_id=user.id,
                    team_name=f"Team {team_id}" if team_id else "General",
                    tasks_completed=tasks_completed,
                    hours_worked=hours_worked,
                    hours_billable=hours_worked * 0.8,
                    utilization_rate=utilization_rate,
                    efficiency_score=efficiency_score,
                    revenue_generated=revenue_generated,
                    cost_incurred=cost_incurred,
                    profit_contribution=profit_contribution,
                    productivity_index=efficiency_score,
                    period_start=period_start,
                    period_end=period_end
                )
                
                db.add(productivity)
                productivity_data.append({
                    "user_id": user.id,
                    "user_name": user.full_name,
                    "tasks_completed": tasks_completed,
                    "hours_worked": hours_worked,
                    "utilization_rate": utilization_rate,
                    "efficiency_score": efficiency_score,
                    "profit_contribution": profit_contribution
                })
            
            db.commit()
            
            return {
                "success": True,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "productivity_data": productivity_data,
                "summary": {
                    "total_users": len(users),
                    "avg_utilization": sum(p["utilization_rate"] for p in productivity_data) / len(productivity_data) if productivity_data else 0,
                    "avg_efficiency": sum(p["efficiency_score"] for p in productivity_data) / len(productivity_data) if productivity_data else 0,
                    "total_profit": sum(p["profit_contribution"] for p in productivity_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating team productivity: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file checksum: {e}")
            return ""
    
    def _encrypt_file(self, file_path: str) -> str:
        """Encrypt file using Fernet encryption"""
        try:
            if not self.encryption_key:
                return file_path
            
            fernet = Fernet(self.encryption_key)
            
            # Read and encrypt file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            encrypted_data = fernet.encrypt(file_data)
            
            # Save encrypted file
            encrypted_path = file_path + ".encrypted"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Remove original file
            os.remove(file_path)
            
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Error encrypting file: {e}")
            return file_path
    
    def get_document_versions(self, db: Session, document_id: int) -> Dict:
        """Get all versions of a document"""
        try:
            documents = db.query(Document).filter(
                or_(Document.id == document_id, Document.parent_document_id == document_id)
            ).order_by(Document.created_at).all()
            
            return {
                "success": True,
                "versions": [
                    {
                        "id": doc.id,
                        "version": doc.version,
                        "filename": doc.filename,
                        "file_size": doc.file_size,
                        "created_at": doc.created_at.isoformat(),
                        "created_by": doc.user_id,
                        "is_latest": doc.is_latest_version,
                        "parent_id": doc.parent_document_id
                    }
                    for doc in documents
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting document versions: {e}")
            return {"success": False, "error": str(e)}

# Global document service instance
document_service = DocumentService()
