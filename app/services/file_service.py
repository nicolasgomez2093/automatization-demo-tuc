import os
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from PIL import Image
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


class FileService:
    """Service for handling file uploads (local or S3)."""
    
    def __init__(self):
        self.use_s3 = settings.USE_S3
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.max_size = settings.MAX_UPLOAD_SIZE
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS.split(',')
        
        # Create upload directory if using local storage
        if not self.use_s3:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            # Create subdirectories
            (self.upload_dir / "images").mkdir(exist_ok=True)
            (self.upload_dir / "documents").mkdir(exist_ok=True)
            (self.upload_dir / "projects").mkdir(exist_ok=True)
        
        # S3 client
        if self.use_s3:
            self.s3_client = boto3.client(
                's3',
                region_name=settings.S3_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            self.bucket = settings.S3_BUCKET
    
    def _validate_file(self, file: UploadFile):
        """Validate file extension and size."""
        # Check extension
        ext = file.filename.split('.')[-1].lower()
        if ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(self.allowed_extensions)}"
            )
        
        # Check size (if available)
        if hasattr(file, 'size') and file.size > self.max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {self.max_size / 1024 / 1024}MB"
            )
    
    def _generate_filename(self, original_filename: str, prefix: str = "") -> str:
        """Generate unique filename."""
        ext = original_filename.split('.')[-1].lower()
        unique_id = str(uuid.uuid4())
        if prefix:
            return f"{prefix}_{unique_id}.{ext}"
        return f"{unique_id}.{ext}"
    
    def _get_file_category(self, filename: str) -> str:
        """Determine file category based on extension."""
        ext = filename.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'images'
        elif ext in ['pdf', 'doc', 'docx']:
            return 'documents'
        elif ext in ['dwg', 'dxf']:
            return 'projects'
        else:
            return 'documents'
    
    async def upload_file(
        self,
        file: UploadFile,
        prefix: str = "",
        organization_id: Optional[int] = None
    ) -> dict:
        """
        Upload file to local storage or S3.
        Returns dict with file info.
        """
        self._validate_file(file)
        
        # Generate filename
        filename = self._generate_filename(file.filename, prefix)
        category = self._get_file_category(filename)
        
        # Add organization to path for isolation
        if organization_id:
            category = f"org_{organization_id}/{category}"
        
        if self.use_s3:
            return await self._upload_to_s3(file, filename, category)
        else:
            return await self._upload_local(file, filename, category)
    
    async def _upload_local(self, file: UploadFile, filename: str, category: str) -> dict:
        """Upload file to local storage."""
        file_path = self.upload_dir / category / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Optimize image if it's an image
        if category.endswith('images'):
            self._optimize_image(file_path)
        
        return {
            "filename": filename,
            "original_filename": file.filename,
            "url": f"/uploads/{category}/{filename}",
            "size": len(content),
            "content_type": file.content_type,
            "storage": "local"
        }
    
    async def _upload_to_s3(self, file: UploadFile, filename: str, category: str) -> dict:
        """Upload file to S3."""
        s3_key = f"{category}/{filename}"
        
        try:
            content = await file.read()
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type,
                ACL='public-read'  # Or 'private' if you want signed URLs
            )
            
            url = f"https://{self.bucket}.s3.{settings.S3_REGION}.amazonaws.com/{s3_key}"
            
            return {
                "filename": filename,
                "original_filename": file.filename,
                "url": url,
                "size": len(content),
                "content_type": file.content_type,
                "storage": "s3",
                "s3_key": s3_key
            }
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")
    
    def _optimize_image(self, file_path: Path, max_width: int = 1920):
        """Optimize image size and quality."""
        try:
            with Image.open(file_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # Save with optimization
                img.save(file_path, optimize=True, quality=85)
        except Exception as e:
            print(f"Image optimization failed: {e}")
    
    async def upload_multiple(
        self,
        files: List[UploadFile],
        prefix: str = "",
        organization_id: Optional[int] = None
    ) -> List[dict]:
        """Upload multiple files."""
        results = []
        for file in files:
            try:
                result = await self.upload_file(file, prefix, organization_id)
                results.append(result)
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "error": str(e),
                    "success": False
                })
        return results
    
    def delete_file(self, file_url: str):
        """Delete file from storage."""
        if self.use_s3:
            # Extract S3 key from URL
            s3_key = file_url.split('.com/')[-1]
            try:
                self.s3_client.delete_object(Bucket=self.bucket, Key=s3_key)
            except ClientError as e:
                print(f"S3 delete failed: {e}")
        else:
            # Delete from local storage
            file_path = self.upload_dir / file_url.replace('/uploads/', '')
            if file_path.exists():
                file_path.unlink()
    
    def get_file_url(self, filename: str, category: str = "documents") -> str:
        """Get public URL for a file."""
        if self.use_s3:
            return f"https://{self.bucket}.s3.{settings.S3_REGION}.amazonaws.com/{category}/{filename}"
        else:
            return f"/uploads/{category}/{filename}"


# Global instance
file_service = FileService()
