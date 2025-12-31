import os
import json
import shutil
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import User, Expense, Attendance, Project, Client, Organization
import logging

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self):
        self.backup_dir = os.getenv("BACKUP_DIR", "backups")
        self.max_backups = int(os.getenv("MAX_BACKUPS", "10"))
        self.compression = os.getenv("BACKUP_COMPRESSION", "zip")  # zip, tar, none
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, db: Session, organization_id: Optional[int] = None) -> Dict:
        """Create a complete backup of the system or specific organization"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            if organization_id:
                backup_name += f"_org_{organization_id}"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            os.makedirs(backup_path, exist_ok=True)

            # Backup database
            db_backup_path = self._backup_database(backup_path, organization_id)
            
            # Backup files
            files_backup_path = self._backup_files(backup_path, organization_id)
            
            # Backup configuration
            config_backup_path = self._backup_configuration(backup_path, organization_id)
            
            # Create metadata
            metadata = self._create_metadata(db, organization_id)
            metadata_path = os.path.join(backup_path, "metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

            # Compress backup
            if self.compression == "zip":
                compressed_path = self._compress_backup(backup_path)
                # Remove uncompressed folder
                shutil.rmtree(backup_path)
                backup_path = compressed_path

            # Clean old backups
            self._cleanup_old_backups(organization_id)

            logger.info(f"Backup created successfully: {backup_path}")
            
            return {
                "success": True,
                "backup_path": backup_path,
                "backup_name": os.path.basename(backup_path),
                "size": self._get_file_size(backup_path),
                "created_at": datetime.now().isoformat(),
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _backup_database(self, backup_path: str, organization_id: Optional[int] = None) -> str:
        """Backup database to JSON files"""
        db_dir = os.path.join(backup_path, "database")
        os.makedirs(db_dir, exist_ok=True)

        # Get all tables data
        tables = {
            'users': User,
            'expenses': Expense,
            'attendance': Attendance,
            'projects': Project,
            'clients': Client,
            'organizations': Organization
        }

        for table_name, model in tables.items():
            try:
                query = db.query(model)
                
                # Filter by organization if specified
                if organization_id and hasattr(model, 'organization_id'):
                    query = query.filter(model.organization_id == organization_id)
                
                records = query.all()
                
                # Convert to JSON-serializable format
                data = []
                for record in records:
                    record_dict = {}
                    for column in record.__table__.columns:
                        value = getattr(record, column.name)
                        if isinstance(value, datetime):
                            record_dict[column.name] = value.isoformat()
                        else:
                            record_dict[column.name] = value
                    data.append(record_dict)
                
                # Save to file
                file_path = os.path.join(db_dir, f"{table_name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Backed up {len(data)} records from {table_name}")

            except Exception as e:
                logger.error(f"Error backing up table {table_name}: {e}")

        return db_dir

    def _backup_files(self, backup_path: str, organization_id: Optional[int] = None) -> str:
        """Backup uploaded files"""
        files_dir = os.path.join(backup_path, "files")
        os.makedirs(files_dir, exist_ok=True)

        # Source uploads directory
        uploads_dir = os.getenv("UPLOAD_DIR", "uploads")
        if os.path.exists(uploads_dir):
            try:
                if organization_id:
                    # Backup only organization-specific files
                    org_uploads_dir = os.path.join(uploads_dir, f"org_{organization_id}")
                    if os.path.exists(org_uploads_dir):
                        shutil.copytree(org_uploads_dir, os.path.join(files_dir, "uploads"))
                else:
                    # Backup all files
                    shutil.copytree(uploads_dir, os.path.join(files_dir, "uploads"))
                
                logger.info("Files backed up successfully")

            except Exception as e:
                logger.error(f"Error backing up files: {e}")

        return files_dir

    def _backup_configuration(self, backup_path: str, organization_id: Optional[int] = None) -> str:
        """Backup configuration files"""
        config_dir = os.path.join(backup_path, "config")
        os.makedirs(config_dir, exist_ok=True)

        # Backup environment variables (non-sensitive)
        env_vars = {}
        sensitive_keys = ['PASSWORD', 'SECRET', 'TOKEN', 'KEY', 'DATABASE_URL']
        
        for key, value in os.environ.items():
            if not any(sensitive in key.upper() for sensitive in sensitive_keys):
                env_vars[key] = value

        env_path = os.path.join(config_dir, "environment.json")
        with open(env_path, 'w', encoding='utf-8') as f:
            json.dump(env_vars, f, indent=2, ensure_ascii=False)

        return config_dir

    def _create_metadata(self, db: Session, organization_id: Optional[int] = None) -> Dict:
        """Create backup metadata"""
        metadata = {
            "backup_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "organization_id": organization_id,
            "compression": self.compression,
            "tables": {},
            "statistics": {}
        }

        # Get table statistics
        tables = {
            'users': User,
            'expenses': Expense,
            'attendance': Attendance,
            'projects': Project,
            'clients': Client,
            'organizations': Organization
        }

        for table_name, model in tables.items():
            try:
                query = db.query(model)
                if organization_id and hasattr(model, 'organization_id'):
                    query = query.filter(model.organization_id == organization_id)
                
                count = query.count()
                metadata["tables"][table_name] = count

            except Exception as e:
                logger.error(f"Error getting statistics for {table_name}: {e}")
                metadata["tables"][table_name] = 0

        # Calculate additional statistics
        try:
            # Total expenses amount
            expenses_query = db.query(Expense)
            if organization_id:
                expenses_query = expenses_query.filter(Expense.organization_id == organization_id)
            total_expenses = sum(exp.amount for exp in expenses_query.all())
            metadata["statistics"]["total_expenses"] = total_expenses

            # Total hours worked
            attendance_query = db.query(Attendance)
            if organization_id:
                attendance_query = attendance_query.filter(Attendance.organization_id == organization_id)
            total_hours = sum(att.hours_worked or 0 for att in attendance_query.all())
            metadata["statistics"]["total_hours"] = total_hours

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")

        return metadata

    def _compress_backup(self, backup_path: str) -> str:
        """Compress backup directory to zip file"""
        zip_path = f"{backup_path}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, backup_path)
                    zipf.write(file_path, arcname)

        return zip_path

    def _cleanup_old_backups(self, organization_id: Optional[int] = None):
        """Remove old backups keeping only the most recent ones"""
        try:
            # List all backup files
            backup_files = []
            for file in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, file)
                if os.path.isfile(file_path) and (file.startswith("backup_") or file.endswith(".zip")):
                    # Check if it's an organization-specific backup
                    if organization_id and f"_org_{organization_id}" not in file:
                        continue
                    if not organization_id and "_org_" in file:
                        continue
                    
                    backup_files.append({
                        'path': file_path,
                        'name': file,
                        'modified': os.path.getmtime(file_path)
                    })

            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x['modified'], reverse=True)

            # Remove old backups
            if len(backup_files) > self.max_backups:
                for backup in backup_files[self.max_backups:]:
                    try:
                        os.remove(backup['path'])
                        logger.info(f"Removed old backup: {backup['name']}")
                    except Exception as e:
                        logger.error(f"Error removing old backup {backup['name']}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")

    def _get_file_size(self, file_path: str) -> str:
        """Get human-readable file size"""
        if not os.path.exists(file_path):
            return "0 B"
        
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def list_backups(self, organization_id: Optional[int] = None) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        try:
            for file in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, file)
                
                # Check if it's a backup file
                if not (file.startswith("backup_") and (file.endswith(".zip") or os.path.isdir(file_path))):
                    continue

                # Filter by organization if specified
                if organization_id and f"_org_{organization_id}" not in file:
                    continue
                if not organization_id and "_org_" in file:
                    continue

                backup_info = {
                    "name": file,
                    "path": file_path,
                    "size": self._get_file_size(file_path),
                    "created": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                    "type": "directory" if os.path.isdir(file_path) else "compressed"
                }

                # Load metadata if available
                metadata_path = os.path.join(file_path, "metadata.json") if os.path.isdir(file_path) else None
                if metadata_path and os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            backup_info["metadata"] = json.load(f)
                    except Exception as e:
                        logger.error(f"Error loading metadata for {file}: {e}")

                backups.append(backup_info)

        except Exception as e:
            logger.error(f"Error listing backups: {e}")

        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups

    def restore_backup(self, backup_path: str, db: Session) -> Dict:
        """Restore data from backup"""
        try:
            # Extract if compressed
            if backup_path.endswith(".zip"):
                extract_path = backup_path[:-4] + "_extracted"
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(extract_path)
                backup_path = extract_path

            # Load metadata
            metadata_path = os.path.join(backup_path, "metadata.json")
            if not os.path.exists(metadata_path):
                return {"success": False, "error": "Metadata not found"}

            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Restore database
            db_path = os.path.join(backup_path, "database")
            if os.path.exists(db_path):
                restore_result = self._restore_database(db_path, db)
                if not restore_result["success"]:
                    return restore_result

            # Restore files
            files_path = os.path.join(backup_path, "files")
            if os.path.exists(files_path):
                self._restore_files(files_path)

            # Cleanup extracted folder if it was extracted
            if extract_path:
                shutil.rmtree(extract_path)

            logger.info(f"Backup restored successfully from {backup_path}")
            
            return {
                "success": True,
                "restored_at": datetime.now().isoformat(),
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return {"success": False, "error": str(e)}

    def _restore_database(self, db_path: str, db: Session) -> Dict:
        """Restore database from JSON files"""
        try:
            tables = {
                'organizations': Organization,
                'users': User,
                'projects': Project,
                'clients': Client,
                'expenses': Expense,
                'attendance': Attendance
            }

            for table_name, model in tables.items():
                file_path = os.path.join(db_path, f"{table_name}.json")
                if not os.path.exists(file_path):
                    continue

                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Clear existing data (be careful with this in production)
                db.query(model).delete()

                # Insert restored data
                for record_data in data:
                    try:
                        # Convert datetime strings back to datetime objects
                        for key, value in record_data.items():
                            if isinstance(value, str) and value.endswith('Z'):
                                try:
                                    record_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                except:
                                    pass
                        
                        record = model(**record_data)
                        db.add(record)

                    except Exception as e:
                        logger.error(f"Error restoring record in {table_name}: {e}")

                db.commit()
                logger.info(f"Restored {len(data)} records to {table_name}")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}

    def _restore_files(self, files_path: str):
        """Restore files from backup"""
        try:
            uploads_dir = os.getenv("UPLOAD_DIR", "uploads")
            backup_uploads = os.path.join(files_path, "uploads")
            
            if os.path.exists(backup_uploads):
                if os.path.exists(uploads_dir):
                    shutil.rmtree(uploads_dir)
                shutil.copytree(backup_uploads, uploads_dir)
                logger.info("Files restored successfully")

        except Exception as e:
            logger.error(f"Error restoring files: {e}")

# Global backup service instance
backup_service = BackupService()
