from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.models.user import User
from app.models.expense import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseStats
from app.api.deps import get_current_user, get_manager_user
from app.services.export_service import export_service

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new expense."""
    print(f"DEBUG: Creating expense for org {current_user.organization_id}, user {current_user.id}")
    print(f"DEBUG: Expense data: {expense_data}")
    
    expense = Expense(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        amount=expense_data.amount,
        category=expense_data.category,
        description=expense_data.description,
        project_id=expense_data.project_id,
        receipt_url=expense_data.receipt_url,
        expense_date=expense_data.expense_date or datetime.utcnow()
    )
    
    db.add(expense)
    db.commit()
    db.refresh(expense)
    
    print(f"DEBUG: Created expense - ID: {expense.id}, Org: {expense.organization_id}, Amount: {expense.amount}")
    return expense


@router.get("/", response_model=List[ExpenseResponse])
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """List expenses with advanced filters (user, project, category, dates)."""
    from datetime import datetime
    
    # Convert empty strings to None and validate types
    user_id = int(user_id) if user_id and user_id.strip() else None
    project_id = int(project_id) if project_id and project_id.strip() else None
    category = category.strip() if category and category.strip() else None
    
    # Parse dates if provided
    if start_date and start_date.strip():
        try:
            start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError:
            start_date = None
    else:
        start_date = None
        
    if end_date and end_date.strip():
        try:
            end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d")
        except ValueError:
            end_date = None
    else:
        end_date = None
    
    query = db.query(Expense).options(
        joinedload(Expense.user),
        joinedload(Expense.project)
    ).filter(Expense.organization_id == current_user.organization_id)
    
    if user_id:
        query = query.filter(Expense.user_id == user_id)
    if category:
        query = query.filter(Expense.category == category)
    if project_id:
        query = query.filter(Expense.project_id == project_id)
    if start_date:
        query = query.filter(Expense.expense_date >= start_date)
    if end_date:
        query = query.filter(Expense.expense_date <= end_date)
    
    expenses = query.order_by(Expense.expense_date.desc()).offset(skip).limit(limit).all()
    return expenses


@router.get("/stats", response_model=ExpenseStats)
async def get_expense_stats(
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Get expense statistics with filters."""
    from datetime import datetime
    
    # Convert empty strings to None and validate types
    user_id = int(user_id) if user_id and user_id.strip() else None
    project_id = int(project_id) if project_id and project_id.strip() else None
    
    # Parse dates if provided
    if start_date and start_date.strip():
        try:
            start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError:
            start_date = None
    else:
        start_date = None
        
    if end_date and end_date.strip():
        try:
            end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d")
        except ValueError:
            end_date = None
    else:
        end_date = None
    
    query = db.query(Expense).filter(Expense.organization_id == current_user.organization_id)
    
    if user_id:
        query = query.filter(Expense.user_id == user_id)
    if project_id:
        query = query.filter(Expense.project_id == project_id)
    if start_date:
        query = query.filter(Expense.expense_date >= start_date)
    if end_date:
        query = query.filter(Expense.expense_date <= end_date)
    
    expenses = query.all()
    
    # Debug logging
    print(f"DEBUG: Found {len(expenses)} expenses for org {current_user.organization_id}")
    for expense in expenses[:3]:  # Log first 3 expenses
        print(f"DEBUG: Expense - ID: {expense.id}, Amount: {expense.amount}, Org: {expense.organization_id}")
    
    total = sum(e.amount for e in expenses)
    
    # Group by category
    by_category = {}
    for expense in expenses:
        cat = expense.category.value if hasattr(expense.category, 'value') else expense.category
        by_category[cat] = by_category.get(cat, 0) + expense.amount
    
    # Group by project
    by_project = {}
    for expense in expenses:
        if expense.project_id:
            by_project[expense.project_id] = by_project.get(expense.project_id, 0) + expense.amount
    
    stats = ExpenseStats(
        total_expenses=round(total, 2),
        by_category=by_category,
        by_project=by_project,
        count=len(expenses)
    )
    
    print(f"DEBUG: Returning stats - Total: {stats.total_expenses}, Count: {stats.count}")
    return stats


@router.get("/export/csv")
async def export_expenses_csv(
    category: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Export expenses to CSV with filters."""
    from datetime import datetime
    
    # Convert empty strings to None and validate types
    user_id = int(user_id) if user_id and user_id.strip() else None
    project_id = int(project_id) if project_id and project_id.strip() else None
    category = category.strip() if category and category.strip() else None
    
    # Parse dates if provided
    if start_date and start_date.strip():
        try:
            start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError:
            start_date = None
    else:
        start_date = None
        
    if end_date and end_date.strip():
        try:
            end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d")
        except ValueError:
            end_date = None
    else:
        end_date = None
    
    query = db.query(Expense).filter(Expense.organization_id == current_user.organization_id)
    
    if user_id:
        query = query.filter(Expense.user_id == user_id)
    if category:
        query = query.filter(Expense.category == category)
    if project_id:
        query = query.filter(Expense.project_id == project_id)
    if start_date:
        query = query.filter(Expense.expense_date >= start_date)
    if end_date:
        query = query.filter(Expense.expense_date <= end_date)
    
    expenses = query.all()
    
    # Convert to dict
    data = [
        {
            "id": e.id,
            "user_id": e.user_id,
            "project_id": e.project_id,
            "amount": e.amount,
            "category": e.category,
            "description": e.description,
            "expense_date": e.expense_date,
            "created_at": e.created_at
        }
        for e in expenses
    ]
    
    csv_buffer = export_service.export_to_csv(data)
    
    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=expenses_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get expense by ID."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.organization_id == current_user.organization_id
    ).first()
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    expense_data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Update expense."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.organization_id == current_user.organization_id
    ).first()
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    update_data = expense_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)
    
    db.commit()
    db.refresh(expense)
    
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Delete expense."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.organization_id == current_user.organization_id
    ).first()
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    db.delete(expense)
    db.commit()
    
    return None
