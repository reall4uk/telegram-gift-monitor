#!/usr/bin/env python3
"""
Authentication Service
Handles JWT tokens and user authentication
"""

import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Handles authentication and JWT token management"""
    
    def __init__(self):
        # In production, load from environment variable
        self.SECRET_KEY = "your-super-secret-jwt-key-change-in-production"
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_HOURS = 24 * 30  # 30 days
        self.REFRESH_TOKEN_EXPIRE_HOURS = 24 * 90  # 90 days
    
    def create_token(self, user_id: int, token_type: str = "access") -> str:
        """
        Create JWT token for user
        
        Args:
            user_id: User ID to encode in token
            token_type: Type of token (access or refresh)
            
        Returns:
            JWT token string
        """
        expire_hours = (
            self.ACCESS_TOKEN_EXPIRE_HOURS 
            if token_type == "access" 
            else self.REFRESH_TOKEN_EXPIRE_HOURS
        )
        
        payload = {
            "user_id": user_id,
            "type": token_type,
            "exp": datetime.utcnow() + timedelta(hours=expire_hours),
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)  # JWT ID for revocation
        }
        
        token = jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)
        logger.info(f"Created {token_type} token for user {user_id}")
        
        return token
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token to verify
            token_type: Expected token type
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.SECRET_KEY, 
                algorithms=[self.ALGORITHM]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Create new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token or None if refresh token invalid
        """
        payload = self.verify_token(refresh_token, token_type="refresh")
        
        if not payload:
            return None
        
        # Create new access token
        return self.create_token(payload["user_id"], token_type="access")
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using SHA256
        Note: In production, use bcrypt or argon2
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            hashed: Hashed password
            
        Returns:
            True if password matches
        """
        return self.hash_password(password) == hashed
    
    def generate_api_key(self, user_id: int) -> str:
        """
        Generate API key for user
        
        Args:
            user_id: User ID
            
        Returns:
            API key
        """
        # Create a unique API key
        data = f"{user_id}:{datetime.utcnow().isoformat()}:{secrets.token_urlsafe(16)}"
        api_key = hashlib.sha256(data.encode()).hexdigest()
        
        return f"tgm_{api_key[:32]}"
    
    def verify_api_key(self, api_key: str) -> bool:
        """
        Verify API key format
        
        Args:
            api_key: API key to verify
            
        Returns:
            True if valid format
        """
        return api_key.startswith("tgm_") and len(api_key) == 36
    
    def create_device_fingerprint(self, device_info: Dict) -> str:
        """
        Create device fingerprint for additional security
        
        Args:
            device_info: Device information dictionary
            
        Returns:
            Device fingerprint hash
        """
        # Combine device identifiers
        fingerprint_data = f"{device_info.get('device_id', '')}:" \
                          f"{device_info.get('device_type', '')}:" \
                          f"{device_info.get('app_version', '')}:" \
                          f"{device_info.get('os_version', '')}"
        
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
    
    def generate_license_signature(self, license_data: Dict) -> str:
        """
        Generate cryptographic signature for license
        
        Args:
            license_data: License information
            
        Returns:
            Signature string
        """
        # Create signature data
        sig_data = f"{license_data['key']}:" \
                   f"{license_data['type']}:" \
                   f"{license_data['expires_at']}:" \
                   f"{self.SECRET_KEY}"
        
        return hashlib.sha512(sig_data.encode()).hexdigest()[:32]
    
    def verify_license_signature(self, license_data: Dict, signature: str) -> bool:
        """
        Verify license signature
        
        Args:
            license_data: License information
            signature: Signature to verify
            
        Returns:
            True if signature valid
        """
        expected_signature = self.generate_license_signature(license_data)
        return secrets.compare_digest(expected_signature, signature)