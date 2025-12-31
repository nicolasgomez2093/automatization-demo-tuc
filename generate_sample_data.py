#!/usr/bin/env python3
"""
Generate sample data for ML training (minimum 30 records required)
"""

import sys
import os
from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.expense import Expense, ExpenseCategory
from app.models.attendance import Attendance
from app.models.project import Project
from app.models.user import User
from app.models.organization import Organization

def generate_sample_data():
    """Generate sample data for ML training"""
    db = SessionLocal()
    
    try:
        # Get default organization
        org = db.query(Organization).filter(Organization.slug == "default").first()
        if not org:
            print("❌ Default organization not found")
            return
        
        print(f"📊 Generating sample data for organization: {org.name}")
        
        # Get admin user
        admin_user = db.query(User).filter(User.organization_id == org.id, User.role == "superadmin").first()
        if not admin_user:
            print("❌ Admin user not found")
            return
        
        # Generate sample projects
        projects = []
        project_names = [
            "Website Redesign", "Mobile App Development", "Database Migration",
            "Cloud Infrastructure", "Security Audit", "API Integration",
            "Data Analytics Platform", "E-commerce Solution", "CRM Implementation",
            "DevOps Pipeline", "Machine Learning Model", "Blockchain Integration"
        ]
        
        for name in project_names:
            existing = db.query(Project).filter(Project.name == name, Project.organization_id == org.id).first()
            if not existing:
                project = Project(
                    organization_id=org.id,
                    name=name,
                    description=f"Sample project for {name}",
                    status=random.choice(["planificacion", "en_progreso", "completado", "pausado"]),
                    start_date=datetime.now() - timedelta(days=random.randint(30, 365)),
                    end_date=datetime.now() + timedelta(days=random.randint(30, 180)),
                    budget=random.uniform(10000, 100000)
                )
                db.add(project)
                projects.append(project)
        
        db.commit()
        
        # Get all existing projects
        projects = db.query(Project).filter(Project.organization_id == org.id).all()
        print(f"📁 Found {len(projects)} projects")
        
        # Generate sample expenses (minimum 30 required)
        expense_categories = [
            "comida", "obra", "transporte", "materiales", 
            "servicios", "salario", "otros"
        ]
        expense_descriptions = [
            "Office Supplies", "Software License", "Cloud Services", "Consulting Fees",
            "Marketing Campaign", "Travel Expenses", "Equipment Purchase", "Training Costs",
            "Insurance Premium", "Legal Services", "Accounting Services", "IT Support",
            "Hardware Maintenance", "Internet Services", "Phone Bills", "Utilities",
            "Rent Payment", "Employee Benefits", "Advertising Costs", "Research Materials",
            "Conference Attendance", "Subscriptions", "Delivery Services", "Printing Costs",
            "Vehicle Expenses", "Entertainment", "Bank Fees", "Tax Preparation",
            "Security Services", "Cleaning Services", "Office Furniture"
        ]
        
        expenses = []
        for i in range(50):  # Generate 50 expenses to ensure we have enough
            existing = db.query(Expense).filter(Expense.description == expense_descriptions[i % len(expense_descriptions)]).first()
            if not existing:
                expense = Expense(
                    organization_id=org.id,
                    user_id=admin_user.id,
                    description=expense_descriptions[i % len(expense_descriptions)],
                    amount=random.uniform(50, 5000),
                    category=random.choice(expense_categories),
                    expense_date=datetime.now() - timedelta(days=random.randint(0, 365)),
                    project_id=random.choice(projects).id if random.random() > 0.3 else None,
                    receipt_url=f"https://example.com/receipt_{i+1}.pdf"
                )
                expenses.append(expense)
        
        # Add all expenses
        for expense in expenses:
            db.add(expense)
        
        db.commit()
        print(f"✅ Created {len(expenses)} expenses")
        
        # Generate sample attendance records
        attendance_records = []
        for days_ago in range(60):  # Generate 60 days of attendance
            date = datetime.now() - timedelta(days=days_ago)
            
            # Random check-in and check-out times for weekdays only
            if date.weekday() < 5:  # Weekdays only
                check_in = date.replace(hour=random.randint(8, 10), minute=random.randint(0, 59))
                check_out = check_in.replace(hour=random.randint(17, 19), minute=random.randint(0, 59))
                hours_worked = (check_out - check_in).total_seconds() / 3600
                
                attendance = Attendance(
                    organization_id=org.id,
                    user_id=admin_user.id,
                    check_in=check_in,
                    check_out=check_out,
                    hours_worked=hours_worked,
                    notes=f"Sample attendance record for {date.strftime('%Y-%m-%d')}"
                )
                attendance_records.append(attendance)
        
        # Add all attendance records
        for record in attendance_records:
            db.add(record)
        
        db.commit()
        print(f"✅ Created {len(attendance_records)} attendance records")
        
        # Summary
        total_expenses = db.query(Expense).filter(Expense.organization_id == org.id).count()
        total_attendance = db.query(Attendance).filter(Attendance.organization_id == org.id).count()
        total_projects = db.query(Project).filter(Project.organization_id == org.id).count()
        
        print("\n📈 Sample Data Summary:")
        print(f"   💰 Expenses: {total_expenses} records")
        print(f"   ⏰ Attendance: {total_attendance} records") 
        print(f"   📁 Projects: {total_projects} records")
        print(f"   ✅ ML training requirements satisfied!")
        
    except Exception as e:
        print(f"❌ Error generating sample data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_sample_data()
