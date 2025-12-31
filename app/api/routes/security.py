from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.security import UserTwoFactor, TwoFactorMethod, AuditLog, SecurityPolicy, UserSession
from app.services.security_service import security_service
from pydantic import BaseModel

router = APIRouter()

class TOTPSetupRequest(BaseModel):
    token: str

class TOTPVerifyRequest(BaseModel):
    token: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class SecurityPolicyRequest(BaseModel):
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_symbols: bool = True
    password_history_count: int = 5
    password_expiry_days: int = 90
    session_timeout_minutes: int = 480
    max_concurrent_sessions: int = 3
    require_2fa: bool = False
    require_2fa_for_admins: bool = False
    allowed_2fa_methods: List[str] = ["totp", "sms", "email"]
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    allowed_ip_ranges: Optional[List[str]] = None
    block_suspicious_ips: bool = True

@router.post("/2fa/setup")
async def setup_2fa(
    request: TOTPSetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Setup 2FA for user - DISABLED"""
    return {
        "success": False,
        "message": "2FA functionality has been disabled in this system",
        "error": "2FA_DISABLED"
    }

@router.post("/2fa/verify")
async def verify_2fa_setup(
    request: TOTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify and enable 2FA - DISABLED"""
    return {
        "success": False,
        "message": "2FA functionality has been disabled in this system",
        "error": "2FA_DISABLED"
    }

@router.post("/2fa/disable")
async def disable_2fa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable 2FA for user - DISABLED"""
    return {
        "success": False,
        "message": "2FA functionality has been disabled in this system",
        "error": "2FA_DISABLED"
    }

@router.get("/2fa/status")
async def get_2fa_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get 2FA status for user - DISABLED"""
    return {
        "success": True,
        "enabled": False,
        "method": None,
        "verified": False,
        "verified_at": None,
        "message": "2FA functionality has been disabled in this system"
    }

@router.post("/password/change")
async def change_password(
    request: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Verify current password
        import bcrypt
        if not bcrypt.checkpw(request.current_password.encode('utf-8'), current_user.password_hash.encode('utf-8')):
            return {
                "success": False,
                "error": "Current password is incorrect"
            }
        
        # Get security policy
        policy_result = security_service.get_security_policy(db, current_user.organization_id)
        if not policy_result["success"]:
            return policy_result
        
        policy_dict = policy_result["policy"]
        policy = SecurityPolicy(**policy_dict)
        
        # Validate new password
        validation_result = security_service.validate_password(request.new_password, policy)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "Password does not meet security requirements",
                "validation_errors": validation_result["errors"]
            }
        
        # Check password history
        history_result = security_service.check_password_history(db, current_user.id, request.new_password)
        if not history_result["valid"]:
            return history_result
        
        # Hash new password
        new_password_hash = bcrypt.hashpw(request.new_password.encode('utf-8'), bcrypt.gensalt()).decode()
        
        # Update user password
        old_password_hash = current_user.password_hash
        current_user.password_hash = new_password_hash
        current_user.updated_at = datetime.utcnow()
        
        # Save to password history
        security_service.save_password_history(db, current_user.id, old_password_hash)
        
        db.commit()
        
        # Log audit event
        security_service.log_audit_event(
            db=db,
            organization_id=current_user.organization_id,
            action=AuditAction.SETTINGS_CHANGE,
            resource_type="password",
            user_id=current_user.id,
            ip_address="0.0.0.0",
            endpoint="/api/security/password/change",
            method="POST"
        )
        
        return {
            "success": True,
            "message": "Password changed successfully"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/policy")
async def get_security_policy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get security policy for organization"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        result = security_service.get_security_policy(db, current_user.organization_id)
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/policy")
async def update_security_policy(
    request: SecurityPolicyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update security policy for organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        # Get existing policy
        policy = db.query(SecurityPolicy).filter(
            SecurityPolicy.organization_id == current_user.organization_id
        ).first()
        
        if not policy:
            policy = SecurityPolicy(organization_id=current_user.organization_id)
            db.add(policy)
        
        # Update policy
        old_values = {
            "password_min_length": policy.password_min_length,
            "require_2fa": policy.require_2fa,
            "session_timeout_minutes": policy.session_timeout_minutes
        }
        
        policy.password_min_length = request.password_min_length
        policy.password_require_uppercase = request.password_require_uppercase
        policy.password_require_lowercase = request.password_require_lowercase
        policy.password_require_numbers = request.password_require_numbers
        policy.password_require_symbols = request.password_require_symbols
        policy.password_history_count = request.password_history_count
        policy.password_expiry_days = request.password_expiry_days
        policy.session_timeout_minutes = request.session_timeout_minutes
        policy.max_concurrent_sessions = request.max_concurrent_sessions
        policy.require_2fa = request.require_2fa
        policy.require_2fa_for_admins = request.require_2fa_for_admins
        policy.allowed_2fa_methods = request.allowed_2fa_methods
        policy.max_login_attempts = request.max_login_attempts
        policy.lockout_duration_minutes = request.lockout_duration_minutes
        policy.allowed_ip_ranges = request.allowed_ip_ranges
        policy.block_suspicious_ips = request.block_suspicious_ips
        policy.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Log audit event
        security_service.log_audit_event(
            db=db,
            organization_id=current_user.organization_id,
            action=AuditAction.SETTINGS_CHANGE,
            resource_type="security_policy",
            user_id=current_user.id,
            ip_address="0.0.0.0",
            endpoint="/api/security/policy",
            method="POST",
            old_values=old_values,
            new_values=request.dict()
        )
        
        return {
            "success": True,
            "message": "Security policy updated successfully"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/sessions")
async def get_user_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user sessions"""
    try:
        result = security_service.get_user_sessions(db, current_user.id)
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke user session"""
    try:
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        result = security_service.revoke_session(db, session.session_token)
        
        if result["success"]:
            # Log audit event
            security_service.log_audit_event(
                db=db,
                organization_id=current_user.organization_id,
                action=AuditAction.SETTINGS_CHANGE,
                resource_type="session",
                resource_id=str(session_id),
                user_id=current_user.id,
                ip_address="0.0.0.0",
                endpoint=f"/api/security/sessions/{session_id}",
                method="DELETE"
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get audit logs"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        query = db.query(AuditLog).filter(
            AuditLog.organization_id == current_user.organization_id
        )
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "logs": [
                {
                    "id": log.id,
                    "action": log.action.value,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                    "endpoint": log.endpoint,
                    "method": log.method,
                    "success": log.success,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ],
            "total": len(logs)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/login-attempts")
async def get_login_attempts(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent login attempts"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        from app.models.security import LoginAttempt
        
        attempts = db.query(LoginAttempt).filter(
            LoginAttempt.created_at >= datetime.utcnow() - timedelta(days=7)
        ).order_by(LoginAttempt.created_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "attempts": [
                {
                    "id": attempt.id,
                    "email": attempt.email,
                    "ip_address": attempt.ip_address,
                    "success": attempt.success,
                    "failure_reason": attempt.failure_reason,
                    "created_at": attempt.created_at.isoformat()
                }
                for attempt in attempts
            ]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# SuperAdmin endpoints
@router.get("/admin/policy/{organization_id}")
async def admin_get_security_policy(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Get security policy for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        result = security_service.get_security_policy(db, organization_id)
        
        if result["success"]:
            result["organization_id"] = organization_id
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }

@router.get("/admin/audit-logs/{organization_id}")
async def admin_get_audit_logs(
    organization_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SuperAdmin: Get audit logs for any organization"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    
    try:
        logs = db.query(AuditLog).filter(
            AuditLog.organization_id == organization_id
        ).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "organization_id": organization_id,
            "logs": [
                {
                    "id": log.id,
                    "action": log.action.value,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                    "endpoint": log.endpoint,
                    "method": log.method,
                    "success": log.success,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ],
            "total": len(logs)
        }
    
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization_id,
            "error": str(e)
        }
