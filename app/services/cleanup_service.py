import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import Expense, Attendance, User, Project, Client
import threading
import time

logger = logging.getLogger(__name__)

class CleanupService:
    def __init__(self):
        self.cleanup_interval = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))  # hours
        self.temp_file_max_age = int(os.getenv("TEMP_FILE_MAX_AGE_DAYS", "7"))  # days
        self.log_max_age = int(os.getenv("LOG_MAX_AGE_DAYS", "30"))  # days
        self.backup_max_age = int(os.getenv("BACKUP_MAX_AGE_DAYS", "90"))  # days
        self.upload_cleanup_enabled = os.getenv("UPLOAD_CLEANUP_ENABLED", "true").lower() == "true"
        self.running = False
        self.thread = None

    def start_scheduler(self):
        """Start the automatic cleanup scheduler"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("Cleanup scheduler started")

    def stop_scheduler(self):
        """Stop the automatic cleanup scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Cleanup scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                self.perform_cleanup()
                # Sleep for cleanup interval
                time.sleep(self.cleanup_interval * 3600)
            except Exception as e:
                logger.error(f"Error in cleanup scheduler: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying

    def perform_cleanup(self, db: Session = None) -> Dict:
        """Perform all cleanup operations"""
        results = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "operations": {}
        }

        try:
            # Clean temporary files
            temp_results = self.cleanup_temp_files()
            results["operations"]["temp_files"] = temp_results

            # Clean old logs
            log_results = self.cleanup_old_logs()
            results["operations"]["logs"] = log_results

            # Clean orphaned uploads
            if self.upload_cleanup_enabled:
                upload_results = self.cleanup_orphaned_uploads(db)
                results["operations"]["uploads"] = upload_results

            # Clean old backups
            backup_results = self.cleanup_old_backups()
            results["operations"]["backups"] = backup_results

            # Clean database records
            if db:
                db_results = self.cleanup_database_records(db)
                results["operations"]["database"] = db_results

            # Calculate total cleaned
            total_files = sum(op.get("files_deleted", 0) for op in results["operations"].values())
            total_size = sum(op.get("space_freed", 0) for op in results["operations"].values())
            
            results["summary"] = {
                "total_files_deleted": total_files,
                "total_space_freed": self._format_bytes(total_size),
                "operations_completed": len([op for op in results["operations"].values() if op.get("success", False)])
            }

            logger.info(f"Cleanup completed: {total_files} files deleted, {self._format_bytes(total_size)} freed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            results["success"] = False
            results["error"] = str(e)

        return results

    def cleanup_temp_files(self) -> Dict:
        """Clean temporary files"""
        result = {"success": True, "files_deleted": 0, "space_freed": 0}
        
        try:
            # Clean system temp directory
            temp_dir = tempfile.gettempdir()
            cutoff_time = datetime.now() - timedelta(days=self.temp_file_max_age)
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            result["files_deleted"] += 1
                            result["space_freed"] += file_size
                    except Exception as e:
                        logger.debug(f"Could not process temp file {file_path}: {e}")

            # Clean app-specific temp directories
            app_temp_dirs = [
                "temp",
                "tmp",
                "cache",
                ".cache",
                "__pycache__"
            ]
            
            for temp_dir_name in app_temp_dirs:
                for root, dirs, files in os.walk(".", topdown=True):
                    # Skip hidden directories and common non-temp directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.git']]
                    
                    if os.path.basename(root) == temp_dir_name:
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if file_time < cutoff_time:
                                    file_size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    result["files_deleted"] += 1
                                    result["space_freed"] += file_size
                            except Exception as e:
                                logger.debug(f"Could not process file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    def cleanup_old_logs(self) -> Dict:
        """Clean old log files"""
        result = {"success": True, "files_deleted": 0, "space_freed": 0}
        
        try:
            cutoff_time = datetime.now() - timedelta(days=self.log_max_age)
            log_dirs = ["logs", "log", ".logs"]
            
            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    for root, dirs, files in os.walk(log_dir):
                        for file in files:
                            if file.endswith(('.log', '.out', '.err')):
                                file_path = os.path.join(root, file)
                                try:
                                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    if file_time < cutoff_time:
                                        file_size = os.path.getsize(file_path)
                                        os.remove(file_path)
                                        result["files_deleted"] += 1
                                        result["space_freed"] += file_size
                                except Exception as e:
                                    logger.debug(f"Could not process log file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning logs: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    def cleanup_orphaned_uploads(self, db: Session) -> Dict:
        """Clean orphaned upload files"""
        result = {"success": True, "files_deleted": 0, "space_freed": 0}
        
        if not db:
            result["success"] = False
            result["error"] = "Database session required"
            return result
        
        try:
            uploads_dir = os.getenv("UPLOAD_DIR", "uploads")
            if not os.path.exists(uploads_dir):
                return result

            # Get all files referenced in database
            referenced_files = set()
            
            # Check expense receipts
            expenses = db.query(Expense).filter(Expense.receipt_url.isnot(None)).all()
            for expense in expenses:
                if expense.receipt_url:
                    filename = expense.receipt_url.split('/')[-1]
                    referenced_files.add(filename)

            # Get all uploaded files
            all_uploaded_files = set()
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    all_uploaded_files.add(file)

            # Find orphaned files
            orphaned_files = all_uploaded_files - referenced_files
            
            for file in orphaned_files:
                for root, dirs, files in os.walk(uploads_dir):
                    if file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            result["files_deleted"] += 1
                            result["space_freed"] += file_size
                            logger.info(f"Deleted orphaned upload: {file_path}")
                        except Exception as e:
                            logger.debug(f"Could not delete orphaned file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning orphaned uploads: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    def cleanup_old_backups(self) -> Dict:
        """Clean old backup files"""
        result = {"success": True, "files_deleted": 0, "space_freed": 0}
        
        try:
            backup_dir = os.getenv("BACKUP_DIR", "backups")
            if not os.path.exists(backup_dir):
                return result

            cutoff_time = datetime.now() - timedelta(days=self.backup_max_age)
            
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    if file.startswith("backup_"):
                        file_path = os.path.join(root, file)
                        try:
                            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                            if file_time < cutoff_time:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                result["files_deleted"] += 1
                                result["space_freed"] += file_size
                                logger.info(f"Deleted old backup: {file_path}")
                        except Exception as e:
                            logger.debug(f"Could not delete backup {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning old backups: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    def cleanup_database_records(self, db: Session) -> Dict:
        """Clean old database records"""
        result = {"success": True, "records_deleted": 0}
        
        try:
            # Clean very old attendance records (older than 2 years)
            cutoff_date = datetime.now() - timedelta(days=730)
            
            old_attendances = db.query(Attendance).filter(
                Attendance.check_in < cutoff_date
            ).count()
            
            if old_attendances > 0:
                db.query(Attendance).filter(
                    Attendance.check_in < cutoff_date
                ).delete()
                result["records_deleted"] += old_attendances
                logger.info(f"Deleted {old_attendances} old attendance records")

            # Clean old soft-deleted records (if implemented)
            # This would depend on your soft delete implementation
            
            db.commit()

        except Exception as e:
            logger.error(f"Error cleaning database records: {e}")
            db.rollback()
            result["success"] = False
            result["error"] = str(e)

        return result

    def get_cleanup_stats(self) -> Dict:
        """Get cleanup statistics and settings"""
        return {
            "scheduler_running": self.running,
            "cleanup_interval_hours": self.cleanup_interval,
            "temp_file_max_age_days": self.temp_file_max_age,
            "log_max_age_days": self.log_max_age,
            "backup_max_age_days": self.backup_max_age,
            "upload_cleanup_enabled": self.upload_cleanup_enabled,
            "temp_directory": tempfile.gettempdir(),
            "next_cleanup": datetime.now() + timedelta(hours=self.cleanup_interval) if self.running else None
        }

    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def manual_cleanup(self, db: Session = None) -> Dict:
        """Trigger manual cleanup"""
        logger.info("Manual cleanup triggered")
        return self.perform_cleanup(db)

# Global cleanup service instance
cleanup_service = CleanupService()
