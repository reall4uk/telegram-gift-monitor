#!/usr/bin/env python3
"""
License Management Service
Handles license generation, validation, and activation
"""

import secrets
import string
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
import base64
import json

from database_docker_adapter import Database
from auth import AuthService

logger = logging.getLogger(__name__)


class LicenseService:
    """Manages software licenses"""
    
    def __init__(self):
        self.db = Database()
        self.auth = AuthService()
        self.PREFIX = "TGMP"  # Telegram Gift Monitor Pro
        
        # License types and their properties
        self.LICENSE_TYPES = {
            "trial": {
                "duration_days": 7,
                "max_channels": 1,
                "max_devices": 1,
                "features": ["basic_monitoring", "standard_sounds"]
            },
            "basic": {
                "duration_days": 30,
                "max_channels": 3,
                "max_devices": 2,
                "features": ["basic_monitoring", "custom_sounds", "history"]
            },
            "pro": {
                "duration_days": 30,
                "max_channels": -1,  # Unlimited
                "max_devices": 5,
                "features": ["all"]
            },
            "lifetime": {
                "duration_days": 36500,  # 100 years
                "max_channels": -1,
                "max_devices": 10,
                "features": ["all", "priority_support", "beta_access"]
            }
        }
    
    def generate_license_key(self, license_type: str = "basic") -> Dict:
        """
        Generate new license key
        
        Args:
            license_type: Type of license to generate
            
        Returns:
            Dictionary with license key and metadata
        """
        if license_type not in self.LICENSE_TYPES:
            raise ValueError(f"Invalid license type: {license_type}")
        
        # Generate key components
        timestamp = int(datetime.utcnow().timestamp())
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
        
        # Create license data for signature
        license_data = {
            "type": license_type,
            "created_at": timestamp,
            "random": random_part
        }
        
        # Generate checksum
        checksum = self._calculate_checksum(license_data)
        
        # Format license key: TGMP-XXXX-XXXX-XXXX-XXXX
        key_parts = [
            self.PREFIX,
            random_part[:4],
            random_part[4:8],
            random_part[8:12],
            checksum[:4].upper()
        ]
        
        license_key = '-'.join(key_parts)
        
        # Calculate expiration
        license_config = self.LICENSE_TYPES[license_type]
        expires_at = datetime.utcnow() + timedelta(days=license_config["duration_days"])
        
        return {
            "key": license_key,
            "type": license_type,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "max_channels": license_config["max_channels"],
            "max_devices": license_config["max_devices"],
            "features": license_config["features"]
        }
    
    def _calculate_checksum(self, data: Dict) -> str:
        """Calculate checksum for license validation"""
        # Create deterministic string from data
        data_str = json.dumps(data, sort_keys=True)
        
        # Add secret salt (change in production)
        salted = f"{data_str}:secret-license-salt-change-this"
        
        # Generate checksum
        return hashlib.sha256(salted.encode()).hexdigest()
    
    async def verify_license(self, license_key: str) -> Dict:
        """
        Verify license key validity
        
        Args:
            license_key: License key to verify
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Basic format validation
            if not self._validate_format(license_key):
                return {
                    "valid": False,
                    "error": "Invalid license format"
                }
            
            # Check if license exists in database
            license_data = await self.db.get_license(license_key)
            
            if not license_data:
                return {
                    "valid": False,
                    "error": "License not found"
                }
            
            # Check if already activated
            if license_data.get("activated_at") and license_data.get("user_id"):
                # Check expiration
                if datetime.fromisoformat(license_data["expires_at"]) < datetime.utcnow():
                    return {
                        "valid": False,
                        "error": "License expired",
                        "expired_at": license_data["expires_at"]
                    }
                
                return {
                    "valid": True,
                    "user_id": license_data["user_id"],
                    "type": license_data["type"],
                    "expires_at": license_data["expires_at"],
                    "activated_at": license_data["activated_at"]
                }
            
            # License valid but not activated
            return {
                "valid": True,
                "type": license_data["type"],
                "max_channels": license_data["max_channels"],
                "max_devices": license_data["max_devices"],
                "duration_days": license_data["duration_days"]
            }
            
        except Exception as e:
            logger.error(f"License verification error: {e}")
            return {
                "valid": False,
                "error": "Verification failed"
            }
    
    def _validate_format(self, license_key: str) -> bool:
        """Validate license key format"""
        parts = license_key.split('-')
        
        if len(parts) != 5:
            return False
        
        if parts[0] != self.PREFIX:
            return False
        
        # Check each part length
        expected_lengths = [4, 4, 4, 4, 4]
        for i, part in enumerate(parts):
            if len(part) != expected_lengths[i]:
                return False
        
        # All parts except prefix should be alphanumeric
        for part in parts[1:]:
            if not part.isalnum():
                return False
        
        return True
    
    async def activate_license(self, license_key: str, user_id: int, device_id: str) -> Dict:
        """
        Activate license for user
        
        Args:
            license_key: License key to activate
            user_id: User ID
            device_id: Device ID
            
        Returns:
            Activation result
        """
        try:
            # Verify license first
            verification = await self.verify_license(license_key)
            
            if not verification["valid"]:
                return {
                    "success": False,
                    "error": verification["error"]
                }
            
            # Check if already activated by another user
            if verification.get("user_id") and verification["user_id"] != user_id:
                return {
                    "success": False,
                    "error": "License already activated by another user"
                }
            
            # Get license data
            license_data = await self.db.get_license(license_key)
            
            # Calculate expiration from activation
            license_config = self.LICENSE_TYPES[license_data["type"]]
            expires_at = datetime.utcnow() + timedelta(days=license_config["duration_days"])
            
            # Activate license
            result = await self.db.activate_license(
                license_key=license_key,
                user_id=user_id,
                device_id=device_id,
                expires_at=expires_at
            )
            
            if result["success"]:
                # Update user's license status
                await self.db.update_user_license_status(user_id, True)
                
                return {
                    "success": True,
                    "expires_at": expires_at.isoformat(),
                    "license_type": license_data["type"],
                    "features": license_config["features"]
                }
            else:
                return {
                    "success": False,
                    "error": "Activation failed"
                }
                
        except Exception as e:
            logger.error(f"License activation error: {e}")
            return {
                "success": False,
                "error": "Activation failed"
            }
    
    async def check_license_limits(self, user_id: int, check_type: str) -> Dict:
        """
        Check if user is within license limits
        
        Args:
            user_id: User ID
            check_type: Type of check (channels, devices)
            
        Returns:
            Check result
        """
        try:
            # Get user's active license
            license_info = await self.db.get_user_license(user_id)
            
            if not license_info or not license_info["is_valid"]:
                return {
                    "allowed": False,
                    "reason": "No valid license"
                }
            
            license_config = self.LICENSE_TYPES.get(license_info["license_type"])
            
            if check_type == "channels":
                current_count = await self.db.get_user_subscriptions_count(user_id)
                max_allowed = license_config["max_channels"]
                
                if max_allowed == -1:  # Unlimited
                    return {"allowed": True, "current": current_count, "max": "unlimited"}
                
                return {
                    "allowed": current_count < max_allowed,
                    "current": current_count,
                    "max": max_allowed
                }
                
            elif check_type == "devices":
                current_count = await self.db.get_user_devices_count(user_id)
                max_allowed = license_config["max_devices"]
                
                return {
                    "allowed": current_count < max_allowed,
                    "current": current_count,
                    "max": max_allowed
                }
            
            return {"allowed": False, "reason": "Invalid check type"}
            
        except Exception as e:
            logger.error(f"License limits check error: {e}")
            return {"allowed": False, "reason": "Check failed"}
    
    async def revoke_license(self, license_key: str, reason: str = "Manual revocation") -> Dict:
        """
        Revoke license
        
        Args:
            license_key: License to revoke
            reason: Revocation reason
            
        Returns:
            Revocation result
        """
        try:
            result = await self.db.revoke_license(license_key, reason)
            
            if result["success"]:
                # Update user's license status if activated
                license_data = await self.db.get_license(license_key)
                if license_data and license_data.get("user_id"):
                    await self.db.update_user_license_status(license_data["user_id"], False)
            
            return result
            
        except Exception as e:
            logger.error(f"License revocation error: {e}")
            return {
                "success": False,
                "error": "Revocation failed"
            }
    
    async def generate_batch_licenses(self, license_type: str, count: int) -> List[Dict]:
        """
        Generate multiple licenses at once
        
        Args:
            license_type: Type of licenses to generate
            count: Number of licenses
            
        Returns:
            List of generated licenses
        """
        licenses = []
        
        for _ in range(count):
            license_data = self.generate_license_key(license_type)
            
            # Save to database
            await self.db.create_license(
                license_key=license_data["key"],
                license_type=license_type,
                max_channels=license_data["max_channels"],
                max_devices=license_data["max_devices"],
                duration_days=self.LICENSE_TYPES[license_type]["duration_days"]
            )
            
            licenses.append(license_data)
        
        logger.info(f"Generated {count} {license_type} licenses")
        return licenses
    
    def export_license_for_distribution(self, license_data: Dict) -> str:
        """
        Export license in a format suitable for distribution
        
        Args:
            license_data: License information
            
        Returns:
            Encoded license string
        """
        # Create compact representation
        export_data = {
            "k": license_data["key"],
            "t": license_data["type"],
            "e": license_data["expires_at"]
        }
        
        # Encode as base64
        json_str = json.dumps(export_data, separators=(',', ':'))
        encoded = base64.b64encode(json_str.encode()).decode()
        
        return f"TGMP:{encoded}"