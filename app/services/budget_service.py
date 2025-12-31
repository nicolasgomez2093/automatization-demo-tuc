from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models.budget import Budget, BudgetTransaction, BudgetAlert, ExpenseRequest, ROIAnalysis, BudgetStatus, BudgetType
from app.models.expense import Expense
from app.models.project import Project
from app.models.user import User
import logging
import json

logger = logging.getLogger(__name__)

class BudgetService:
    def __init__(self):
        pass
    
    def create_budget(
        self,
        db: Session,
        organization_id: int,
        name: str,
        description: str,
        budget_type: BudgetType,
        total_amount: float,
        start_date: datetime,
        end_date: datetime,
        created_by: int,
        project_id: Optional[int] = None,
        warning_threshold: float = 80.0,
        critical_threshold: float = 95.0,
        requires_approval: bool = False,
        approver_id: Optional[int] = None,
        max_single_expense: Optional[float] = None
    ) -> Dict:
        """Create a new budget"""
        try:
            # Validate dates
            if start_date >= end_date:
                return {
                    "success": False,
                    "error": "End date must be after start date"
                }
            
            # Check for overlapping budgets for same project/period
            if project_id:
                existing = db.query(Budget).filter(
                    Budget.organization_id == organization_id,
                    Budget.project_id == project_id,
                    Budget.status != BudgetStatus.COMPLETED,
                    or_(
                        and_(Budget.start_date <= start_date, Budget.end_date >= start_date),
                        and_(Budget.start_date <= end_date, Budget.end_date >= end_date),
                        and_(Budget.start_date >= start_date, Budget.end_date <= end_date)
                    )
                ).first()
                
                if existing:
                    return {
                        "success": False,
                        "error": f"Project already has an active budget: {existing.name}"
                    }
            
            # Create budget
            budget = Budget(
                organization_id=organization_id,
                name=name,
                description=description,
                type=budget_type,
                total_amount=total_amount,
                remaining_amount=total_amount,
                start_date=start_date,
                end_date=end_date,
                project_id=project_id,
                warning_threshold=warning_threshold,
                critical_threshold=critical_threshold,
                requires_approval=requires_approval,
                approver_id=approver_id,
                max_single_expense=max_single_expense,
                created_by=created_by,
                status=BudgetStatus.ACTIVE
            )
            
            db.add(budget)
            db.commit()
            db.refresh(budget)
            
            return {
                "success": True,
                "budget": {
                    "id": budget.id,
                    "name": budget.name,
                    "type": budget.type.value,
                    "total_amount": budget.total_amount,
                    "remaining_amount": budget.remaining_amount,
                    "utilization_percentage": budget.utilization_percentage,
                    "status": budget.status.value
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating budget: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_budget_spending(self, db: Session, budget_id: int, expense_amount: float, expense_id: int = None) -> Dict:
        """Update budget spending when expense is created"""
        try:
            budget = db.query(Budget).filter(Budget.id == budget_id).first()
            if not budget:
                return {
                    "success": False,
                    "error": "Budget not found"
                }
            
            # Update spent amount
            old_spent = budget.spent_amount
            budget.spent_amount += expense_amount
            budget.remaining_amount = budget.total_amount - budget.spent_amount
            budget.updated_at = datetime.utcnow()
            
            # Create transaction record
            transaction = BudgetTransaction(
                budget_id=budget_id,
                organization_id=budget.organization_id,
                amount=expense_amount,
                transaction_type="expense",
                expense_id=expense_id,
                created_by=budget.created_by
            )
            db.add(transaction)
            
            # Check thresholds and create alerts
            alerts_created = []
            
            if budget.utilization_percentage >= budget.critical_threshold and not budget.is_critical_threshold_exceeded:
                alert = BudgetAlert(
                    budget_id=budget_id,
                    organization_id=budget.organization_id,
                    alert_type="critical",
                    threshold_percentage=budget.critical_threshold,
                    current_percentage=budget.utilization_percentage
                )
                db.add(alert)
                alerts_created.append("critical")
                
                # Update status if exceeded
                if budget.is_over_budget:
                    budget.status = BudgetStatus.EXCEEDED
            
            elif budget.utilization_percentage >= budget.warning_threshold and not budget.is_warning_threshold_exceeded:
                alert = BudgetAlert(
                    budget_id=budget_id,
                    organization_id=budget.organization_id,
                    alert_type="warning",
                    threshold_percentage=budget.warning_threshold,
                    current_percentage=budget.utilization_percentage
                )
                db.add(alert)
                alerts_created.append("warning")
            
            db.commit()
            
            return {
                "success": True,
                "old_spent": old_spent,
                "new_spent": budget.spent_amount,
                "utilization_percentage": budget.utilization_percentage,
                "alerts_created": alerts_created,
                "status": budget.status.value
            }
            
        except Exception as e:
            logger.error(f"Error updating budget spending: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_budget_status(self, db: Session, budget_id: int) -> Dict:
        """Get current budget status and alerts"""
        try:
            budget = db.query(Budget).filter(Budget.id == budget_id).first()
            if not budget:
                return {
                    "success": False,
                    "error": "Budget not found"
                }
            
            # Get recent transactions
            recent_transactions = db.query(BudgetTransaction).filter(
                BudgetTransaction.budget_id == budget_id
            ).order_by(BudgetTransaction.created_at.desc()).limit(10).all()
            
            # Get active alerts
            active_alerts = db.query(BudgetAlert).filter(
                BudgetAlert.budget_id == budget_id,
                BudgetAlert.is_acknowledged == False
            ).order_by(BudgetAlert.created_at.desc()).all()
            
            # Calculate spending trend
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_spending = db.query(func.sum(BudgetTransaction.amount)).filter(
                BudgetTransaction.budget_id == budget_id,
                BudgetTransaction.created_at >= thirty_days_ago
            ).scalar() or 0
            
            return {
                "success": True,
                "budget": {
                    "id": budget.id,
                    "name": budget.name,
                    "total_amount": budget.total_amount,
                    "spent_amount": budget.spent_amount,
                    "remaining_amount": budget.remaining_amount,
                    "utilization_percentage": budget.utilization_percentage,
                    "status": budget.status.value,
                    "warning_threshold": budget.warning_threshold,
                    "critical_threshold": budget.critical_threshold,
                    "is_warning_exceeded": budget.is_warning_threshold_exceeded,
                    "is_critical_exceeded": budget.is_critical_threshold_exceeded,
                    "is_over_budget": budget.is_over_budget
                },
                "recent_transactions": [
                    {
                        "id": t.id,
                        "amount": t.amount,
                        "type": t.transaction_type,
                        "description": t.description,
                        "created_at": t.created_at.isoformat()
                    }
                    for t in recent_transactions
                ],
                "active_alerts": [
                    {
                        "id": a.id,
                        "type": a.alert_type,
                        "threshold": a.threshold_percentage,
                        "current": a.current_percentage,
                        "created_at": a.created_at.isoformat()
                    }
                    for a in active_alerts
                ],
                "spending_trend": {
                    "last_30_days": recent_spending,
                    "daily_average": recent_spending / 30
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_expense_request(
        self,
        db: Session,
        organization_id: int,
        title: str,
        description: str,
        amount: float,
        category: str,
        budget_id: Optional[int],
        requested_by: int,
        receipt_url: Optional[str] = None,
        supporting_documents: Optional[List[str]] = None
    ) -> Dict:
        """Create an expense request for approval"""
        try:
            # Validate budget if specified
            if budget_id:
                budget = db.query(Budget).filter(
                    Budget.id == budget_id,
                    Budget.organization_id == organization_id
                ).first()
                
                if not budget:
                    return {
                        "success": False,
                        "error": "Budget not found"
                    }
                
                # Check if amount exceeds budget limits
                if budget.max_single_expense and amount > budget.max_single_expense:
                    return {
                        "success": False,
                        "error": f"Amount exceeds maximum single expense limit of ${budget.max_single_expense}"
                    }
                
                if budget.remaining_amount < amount:
                    return {
                        "success": False,
                        "error": "Insufficient budget remaining"
                    }
            
            # Create expense request
            expense_request = ExpenseRequest(
                organization_id=organization_id,
                title=title,
                description=description,
                amount=amount,
                category=category,
                budget_id=budget_id,
                requested_by=requested_by,
                receipt_url=receipt_url,
                supporting_documents=json.dumps(supporting_documents or []),
                status="pending"
            )
            
            db.add(expense_request)
            db.commit()
            db.refresh(expense_request)
            
            # Send notification to approver if budget requires approval
            if budget_id and budget.requires_approval and budget.approver_id:
                # This would integrate with notification service
                logger.info(f"Expense request {expense_request.id} requires approval by user {budget.approver_id}")
            
            return {
                "success": True,
                "expense_request": {
                    "id": expense_request.id,
                    "title": expense_request.title,
                    "amount": expense_request.amount,
                    "status": expense_request.status,
                    "created_at": expense_request.created_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating expense request: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def approve_expense_request(
        self,
        db: Session,
        request_id: int,
        approved_by: int,
        approved: bool = True,
        rejection_reason: Optional[str] = None
    ) -> Dict:
        """Approve or reject an expense request"""
        try:
            expense_request = db.query(ExpenseRequest).filter(ExpenseRequest.id == request_id).first()
            if not expense_request:
                return {
                    "success": False,
                    "error": "Expense request not found"
                }
            
            if expense_request.status != "pending":
                return {
                    "success": False,
                    "error": "Expense request is not pending"
                }
            
            # Update request
            expense_request.status = "approved" if approved else "rejected"
            expense_request.approved_by = approved_by
            expense_request.approved_at = datetime.utcnow()
            expense_request.rejection_reason = rejection_reason
            expense_request.updated_at = datetime.utcnow()
            
            # If approved, create the actual expense
            if approved:
                expense = Expense(
                    organization_id=expense_request.organization_id,
                    amount=expense_request.amount,
                    description=expense_request.description,
                    category=expense_request.category,
                    receipt_url=expense_request.receipt_url,
                    project_id=None,  # Would be set from budget if needed
                    user_id=expense_request.requested_by,
                    created_at=datetime.utcnow()
                )
                
                db.add(expense)
                db.flush()  # Get the expense ID
                
                # Update budget if applicable
                if expense_request.budget_id:
                    budget_result = self.update_budget_spending(
                        db, expense_request.budget_id, expense_request.amount, expense.id
                    )
                    
                    if not budget_result["success"]:
                        db.rollback()
                        return budget_result
            
            db.commit()
            
            return {
                "success": True,
                "status": expense_request.status,
                "approved_at": expense_request.approved_at.isoformat() if expense_request.approved_at else None
            }
            
        except Exception as e:
            logger.error(f"Error approving expense request: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def calculate_project_roi(
        self,
        db: Session,
        organization_id: int,
        project_id: int,
        analysis_start_date: datetime,
        analysis_end_date: datetime,
        total_investment: float,
        revenue_streams: List[Dict],
        cost_breakdown: List[Dict],
        assumptions: str,
        created_by: int
    ) -> Dict:
        """Calculate ROI analysis for a project"""
        try:
            # Validate project exists
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.organization_id == organization_id
            ).first()
            
            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }
            
            # Calculate total return from revenue streams
            total_return = sum(stream.get("amount", 0) for stream in revenue_streams)
            
            # Calculate ROI percentage
            roi_percentage = ((total_return - total_investment) / total_investment * 100) if total_investment > 0 else 0
            
            # Calculate payback period (simplified)
            monthly_return = total_return / 12  # Simplified calculation
            payback_period_months = int(total_investment / monthly_return) if monthly_return > 0 else None
            
            # Create ROI analysis record
            roi_analysis = ROIAnalysis(
                organization_id=organization_id,
                project_id=project_id,
                total_investment=total_investment,
                total_return=total_return,
                roi_percentage=roi_percentage,
                payback_period_months=payback_period_months,
                analysis_start_date=analysis_start_date,
                analysis_end_date=analysis_end_date,
                revenue_streams=json.dumps(revenue_streams),
                cost_breakdown=json.dumps(cost_breakdown),
                assumptions=assumptions,
                status="active",
                created_by=created_by
            )
            
            db.add(roi_analysis)
            db.commit()
            db.refresh(roi_analysis)
            
            return {
                "success": True,
                "roi_analysis": {
                    "id": roi_analysis.id,
                    "total_investment": roi_analysis.total_investment,
                    "total_return": roi_analysis.total_return,
                    "roi_percentage": roi_analysis.roi_percentage,
                    "payback_period_months": roi_analysis.payback_period_months,
                    "status": roi_analysis.status
                },
                "metrics": {
                    "profit_loss": total_return - total_investment,
                    "roi_percentage": roi_percentage,
                    "payback_period_months": payback_period_months,
                    "profit_margin": (total_return - total_investment) / total_return * 100 if total_return > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating ROI: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_budget_dashboard(self, db: Session, organization_id: int) -> Dict:
        """Get budget dashboard data"""
        try:
            # Get all budgets for organization
            budgets = db.query(Budget).filter(
                Budget.organization_id == organization_id
            ).all()
            
            # Calculate totals
            total_budgeted = sum(b.total_amount for b in budgets)
            total_spent = sum(b.spent_amount for b in budgets)
            total_remaining = sum(b.remaining_amount for b in budgets)
            
            # Get budgets by status
            budgets_by_status = {}
            for status in BudgetStatus:
                budgets_by_status[status.value] = len([b for b in budgets if b.status == status])
            
            # Get active alerts
            active_alerts = db.query(BudgetAlert).join(Budget).filter(
                Budget.organization_id == organization_id,
                BudgetAlert.is_acknowledged == False
            ).count()
            
            # Get pending expense requests
            pending_requests = db.query(ExpenseRequest).filter(
                ExpenseRequest.organization_id == organization_id,
                ExpenseRequest.status == "pending"
            ).count()
            
            # Get top budgets by utilization
            budget_utilizations = [
                {
                    "id": b.id,
                    "name": b.name,
                    "utilization": b.utilization_percentage,
                    "status": b.status.value
                }
                for b in budgets
            ]
            budget_utilizations.sort(key=lambda x: x["utilization"], reverse=True)
            
            return {
                "success": True,
                "summary": {
                    "total_budgets": len(budgets),
                    "total_budgeted": total_budgeted,
                    "total_spent": total_spent,
                    "total_remaining": total_remaining,
                    "overall_utilization": (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0
                },
                "budgets_by_status": budgets_by_status,
                "alerts": {
                    "active_count": active_alerts,
                    "pending_requests": pending_requests
                },
                "top_utilizations": budget_utilizations[:10]
            }
            
        except Exception as e:
            logger.error(f"Error getting budget dashboard: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global budget service instance
budget_service = BudgetService()
