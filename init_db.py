"""
Script to initialize the database tables.
Run this after setting up the database for the first time.
Then run init_db_with_orgs.py to create organizations and users.
"""
from app.core.database import engine, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database tables."""
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully!")
        logger.info("")
        logger.info("Next step: Run 'python init_db_with_orgs.py' to create organizations and users")
        
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise


if __name__ == "__main__":
    init_db()
