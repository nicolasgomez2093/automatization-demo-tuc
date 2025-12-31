import secrets
import hashlib
import pyotp
import qrcode
import io
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from app.models.security import (
    UserTwoFactor, TwoFactorMethod, AuditLog, AuditAction, LoginAttempt,
    SecurityPolicy, PasswordHistory, UserSession, SSOProvider, UserSSO
)
from app.models.user import User
from app.core.config import settings
import bcrypt

logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
    
    def setup_totp(self, db: Session, user_id: int) -> Dict:
        """Setup TOTP (Time-based One-Time Password) for user"""
        try:
            # Generate secret
            secret = pyotp.random_base32()
            
            # Generate provisioning URI
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name="Sistema de Gestión Empresarial"
            )
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(totp_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Store secret temporarily (not enabled yet)
            existing_2fa = db.query(UserTwoFactor).filter(UserTwoFactor.user_id == user_id).first()
            
            if existing_2fa:
                existing_2fa.secret = secret
                existing_2fa.method = TwoFactorMethod.TOTP
                existing_2fa.is_verified = False
                existing_2fa.verified_at = None
            else:
                existing_2fa = UserTwoFactor(
                    user_id=user_id,
                    method=TwoFactorMethod.TOTP,
                    secret=secret,
                    is_verified=False
                )
                db.add(existing_2fa)
            
            db.commit()
            
            return {
                "success": True,
                "secret": secret,
                "qr_code": f"data:image/png;base64,{qr_code_base64}",
                "backup_codes": self._generate_backup_codes()
            }
            
        except Exception as e:
            logger.error(f"Error setting up TOTP: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def verify_totp(self, db: Session, user_id: int, token: str) -> Dict:
        """Verify TOTP token and enable 2FA"""
        try:
            user_2fa = db.query(UserTwoFactor).filter(UserTwoFactor.user_id == user_id).first()
            if not user_2fa or not user_2fa.secret:
                return {"success": False, "error": "TOTP not set up"}
            
            # Verify token
            totp = pyotp.TOTP(user_2fa.secret)
            if not totp.verify(token, valid_window=1):
                return {"success": False, "error": "Invalid token"}
            
            # Enable 2FA
            user_2fa.is_enabled = True
            user_2fa.is_verified = True
            user_2fa.verified_at = datetime.utcnow()
            user_2fa.backup_codes = self._generate_backup_codes()
            
            db.commit()
            
            return {
                "success": True,
                "message": "2FA enabled successfully",
                "backup_codes": user_2fa.backup_codes
            }
            
        except Exception as e:
            logger.error(f"Error verifying TOTP: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def verify_2fa_token(self, db: Session, user_id: int, token: str) -> Dict:
        """Verify 2FA token for login"""
        try:
            user_2fa = db.query(UserTwoFactor).filter(
                UserTwoFactor.user_id == user_id,
                UserTwoFactor.is_enabled == True
            ).first()
            
            if not user_2fa:
                return {"success": False, "error": "2FA not enabled"}
            
            # Check backup codes first
            if user_2fa.backup_codes and token in user_2fa.backup_codes:
                # Remove used backup code
                user_2fa.backup_codes.remove(token)
                db.commit()
                return {"success": True, "method": "backup_code"}
            
            # Verify TOTP
            if user_2fa.method == TwoFactorMethod.TOTP and user_2fa.secret:
                totp = pyotp.TOTP(user_2fa.secret)
                if totp.verify(token, valid_window=1):
                    return {"success": True, "method": "totp"}
            
            return {"success": False, "error": "Invalid token"}
            
        except Exception as e:
            logger.error(f"Error verifying 2FA token: {e}")
            return {"success": False, "error": str(e)}
    
    def disable_2fa(self, db: Session, user_id: int) -> Dict:
        """Disable 2FA for user"""
        try:
            user_2fa = db.query(UserTwoFactor).filter(UserTwoFactor.user_id == user_id).first()
            if user_2fa:
                user_2fa.is_enabled = False
                user_2fa.secret = None
                user_2fa.backup_codes = None
                user_2fa.is_verified = False
                user_2fa.verified_at = None
            
            db.commit()
            
            return {"success": True, "message": "2FA disabled successfully"}
            
        except Exception as e:
            logger.error(f"Error disabling 2FA: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def log_audit_event(
        self,
        db: Session,
        organization_id: int,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: str = "0.0.0.0",
        user_agent: str = "",
        endpoint: str = "",
        method: str = "",
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Dict:
        """Log audit event"""
        try:
            audit_log = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                method=method,
                old_values=old_values,
                new_values=new_values,
                success=success,
                error_message=error_message
            )
            
            db.add(audit_log)
            db.commit()
            
            return {"success": True, "audit_id": audit_log.id}
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            return {"success": False, "error": str(e)}
    
    def check_login_attempts(self, db: Session, email: str, ip_address: str) -> Dict:
        """Check if login should be blocked due to too many attempts"""
        try:
            # Count recent failed attempts
            recent_attempts = db.query(LoginAttempt).filter(
                LoginAttempt.email == email,
                LoginAttempt.success == False,
                LoginAttempt.created_at >= datetime.utcnow() - self.lockout_duration
            ).count()
            
            if recent_attempts >= self.max_login_attempts:
                return {
                    "blocked": True,
                    "attempts": recent_attempts,
                    "lockout_duration_minutes": int(self.lockout_duration.total_seconds() / 60)
                }
            
            return {
                "blocked": False,
                "attempts": recent_attempts,
                "remaining_attempts": self.max_login_attempts - recent_attempts
            }
            
        except Exception as e:
            logger.error(f"Error checking login attempts: {e}")
            return {"blocked": False, "error": str(e)}
    
    def record_login_attempt(
        self,
        db: Session,
        email: str,
        ip_address: str,
        user_agent: str = "",
        success: bool = True,
        failure_reason: Optional[str] = None
    ) -> Dict:
        """Record login attempt"""
        try:
            login_attempt = LoginAttempt(
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason
            )
            
            db.add(login_attempt)
            db.commit()
            
            return {"success": True, "attempt_id": login_attempt.id}
            
        except Exception as e:
            logger.error(f"Error recording login attempt: {e}")
            return {"success": False, "error": str(e)}
    
    def validate_password(self, password: str, policy: SecurityPolicy) -> Dict:
        """Validate password against security policy"""
        errors = []
        
        # Length
        if len(password) < policy.password_min_length:
            errors.append(f"Password must be at least {policy.password_min_length} characters long")
        
        # Uppercase
        if policy.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        # Lowercase
        if policy.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        # Numbers
        if policy.password_require_numbers and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        # Symbols
        if policy.password_require_symbols and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def check_password_history(self, db: Session, user_id: int, new_password: str) -> Dict:
        """Check if password was used before"""
        try:
            # Get password history
            password_history = db.query(PasswordHistory).filter(
                PasswordHistory.user_id == user_id
            ).order_by(desc(PasswordHistory.created_at)).limit(10).all()
            
            for history in password_history:
                if bcrypt.checkpw(new_password.encode('utf-8'), history.password_hash.encode('utf-8')):
                    return {
                        "valid": False,
                        "error": "Password was used recently. Please choose a different password."
                    }
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"Error checking password history: {e}")
            return {"valid": True, "error": str(e)}
    
    def save_password_history(self, db: Session, user_id: int, password_hash: str) -> Dict:
        """Save password to history"""
        try:
            # Add new password to history
            password_history = PasswordHistory(
                user_id=user_id,
                password_hash=password_hash
            )
            db.add(password_history)
            
            # Keep only last 10 passwords
            histories = db.query(PasswordHistory).filter(
                PasswordHistory.user_id == user_id
            ).order_by(desc(PasswordHistory.created_at)).offset(10).all()
            
            for history in histories:
                db.delete(history)
            
            db.commit()
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error saving password history: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def create_user_session(
        self,
        db: Session,
        user_id: int,
        organization_id: int,
        ip_address: str,
        user_agent: str = "",
        device_info: Optional[Dict] = None
    ) -> Dict:
        """Create user session"""
        try:
            # Generate tokens
            session_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            
            # Get session timeout from security policy
            policy = db.query(SecurityPolicy).filter(
                SecurityPolicy.organization_id == organization_id
            ).first()
            
            timeout_minutes = policy.session_timeout_minutes if policy else 480
            expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
            
            # Create session
            session = UserSession(
                user_id=user_id,
                organization_id=organization_id,
                session_token=session_token,
                refresh_token=refresh_token,
                device_id=device_info.get("device_id") if device_info else None,
                device_name=device_info.get("device_name") if device_info else None,
                device_type=device_info.get("device_type") if device_info else None,
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=expires_at
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            return {
                "success": True,
                "session_token": session_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat(),
                "session_id": session.id
            }
            
        except Exception as e:
            logger.error(f"Error creating user session: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def validate_session(self, db: Session, session_token: str) -> Dict:
        """Validate user session"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).first()
            
            if not session:
                return {"success": False, "error": "Invalid or expired session"}
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            db.commit()
            
            return {
                "success": True,
                "user_id": session.user_id,
                "organization_id": session.organization_id,
                "session_id": session.id
            }
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return {"success": False, "error": str(e)}
    
    def revoke_session(self, db: Session, session_token: str) -> Dict:
        """Revoke user session"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()
            
            if not session:
                return {"success": False, "error": "Session not found"}
            
            session.is_active = False
            db.commit()
            
            return {"success": True, "message": "Session revoked"}
            
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return {"success": False, "error": str(e)}
    
    def get_user_sessions(self, db: Session, user_id: int) -> Dict:
        """Get all active sessions for user"""
        try:
            sessions = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).order_by(desc(UserSession.last_activity)).all()
            
            return {
                "success": True,
                "sessions": [
                    {
                        "id": s.id,
                        "device_name": s.device_name,
                        "device_type": s.device_type,
                        "ip_address": s.ip_address,
                        "created_at": s.created_at.isoformat(),
                        "last_activity": s.last_activity.isoformat(),
                        "expires_at": s.expires_at.isoformat(),
                        "is_current": True  # This would be determined by comparing with current session
                    }
                    for s in sessions
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_backup_codes(self) -> List[str]:
        """Generate backup codes for 2FA"""
        codes = []
        for _ in range(10):
            code = ''.join(secrets.choice('0123456789') for _ in range(8))
            codes.append(code)
        return codes
    
    def get_security_policy(self, db: Session, organization_id: int) -> Dict:
        """Get security policy for organization"""
        try:
            policy = db.query(SecurityPolicy).filter(
                SecurityPolicy.organization_id == organization_id
            ).first()
            
            if not policy:
                # Create default policy
                policy = SecurityPolicy(organization_id=organization_id)
                db.add(policy)
                db.commit()
                db.refresh(policy)
            
            return {
                "success": True,
                "policy": {
                    "password_min_length": policy.password_min_length,
                    "password_require_uppercase": policy.password_require_uppercase,
                    "password_require_lowercase": policy.password_require_lowercase,
                    "password_require_numbers": policy.password_require_numbers,
                    "password_require_symbols": policy.password_require_symbols,
                    "password_history_count": policy.password_history_count,
                    "password_expiry_days": policy.password_expiry_days,
                    "session_timeout_minutes": policy.session_timeout_minutes,
                    "max_concurrent_sessions": policy.max_concurrent_sessions,
                    "require_2fa": policy.require_2fa,
                    "require_2fa_for_admins": policy.require_2fa_for_admins,
                    "allowed_2fa_methods": policy.allowed_2fa_methods,
                    "max_login_attempts": policy.max_login_attempts,
                    "lockout_duration_minutes": policy.lockout_duration_minutes,
                    "allowed_ip_ranges": policy.allowed_ip_ranges,
                    "block_suspicious_ips": policy.block_suspicious_ips
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting security policy: {e}")
            return {"success": False, "error": str(e)}

# Global security service instance
security_service = SecurityService()
