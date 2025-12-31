#!/usr/bin/env python3
"""Migration script to add organization_id to attendances table."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from sqlalchemy import text

def migrate():
    """Add organization_id column to attendances table."""
    try:
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(attendances)"))
            columns = [row[1] for row in result]
            
            if 'organization_id' in columns:
                print("Column 'organization_id' already exists in attendances table.")
                return
            
            print("Adding organization_id column to attendances table...")
            
            # Add the column
            conn.execute(text("ALTER TABLE attendances ADD COLUMN organization_id INTEGER NOT NULL DEFAULT 1"))
            
            # Create index
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_attendances_organization_id ON attendances(organization_id)"))
            
            conn.commit()
            print("Migration completed successfully!")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate()
