#!/usr/bin/env python3
"""
Push Notification Service
Handles sending push notifications via Firebase Cloud Messaging
"""

import logging
import json
from typing import List, Dict, Optional
import firebase_admin
from firebase_admin import credentials, messaging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Manages push notifications through FCM"""
    
    def __init__(self):
        self.initialized = False
        self.app = None
    
    async def initialize(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if already initialized
            if self.initialized:
                return
            
            # Get credentials from environment
            firebase_creds = os.getenv('FIREBASE_CREDENTIALS')
            
            if not firebase_creds:
                logger.warning("Firebase credentials not found. Push notifications disabled.")
                return
            
            # Parse credentials
            cred_dict = json.loads(firebase_creds)
            cred = credentials.Certificate(cred_dict)
            
            # Initialize app
            self.app = firebase_admin.initialize_app(cred)
            self.initialized = True
            
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            self.initialized = False
    
    async def send_to_token(self, token: str, title: str, body: str, 
                           data: Dict = None, priority: str = "high") -> bool:
        """
        Send notification to a single FCM token
        
        Args:
            token: FCM registration token
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: Notification priority (high/normal)
            
        Returns:
            True if successful
        """
        if not self.initialized:
            logger.error("Firebase not initialized")
            return False
        
        try:
            # Create Android config with high priority
            android_config = messaging.AndroidConfig(
                priority='high' if priority == 'high' else 'normal',
                notification=messaging.AndroidNotification(
                    sound='alarm_sound',
                    channel_id='gift_alerts',
                    priority='max' if priority == 'high' else 'high',
                    default_sound=False,
                    default_vibrate_timings=False,
                    vibrate_timings=[0, 1000, 500, 1000] if priority == 'high' else [0, 500],
                    visibility='public',
                    notification_count=1,
                ),
                data=data or {}
            )
            
            # Create iOS config
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body
                        ),
                        sound=messaging.CriticalSound(
                            name='alarm_sound.caf',
                            critical=True if priority == 'high' else False,
                            volume=1.0 if priority == 'high' else 0.7
                        ),
                        badge=1,
                        content_available=True,
                        mutable_content=True
                    )
                ),
                headers={
                    'apns-priority': '10' if priority == 'high' else '5',
                    'apns-push-type': 'alert'
                }
            )
            
            # Create the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=self._prepare_data(data),
                token=token,
                android=android_config,
                apns=apns_config
            )
            
            # Send the message
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return True
            
        except messaging.UnregisteredError:
            logger.warning(f"Token {token} is not registered")
            return False
        except Exception as e:
            logger.error(f"Error sending message to {token}: {e}")
            return False
    
    async def send_to_tokens(self, tokens: List[str], title: str, body: str,
                            data: Dict = None, priority: str = "high") -> Dict:
        """
        Send notification to multiple FCM tokens
        
        Args:
            tokens: List of FCM tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: Notification priority
            
        Returns:
            Dictionary with success/failure counts
        """
        if not self.initialized:
            logger.error("Firebase not initialized")
            return {"success": 0, "failure": len(tokens)}
        
        if not tokens:
            return {"success": 0, "failure": 0}
        
        # Remove duplicates
        tokens = list(set(tokens))
        
        # Prepare batch message
        android_config = messaging.AndroidConfig(
            priority='high' if priority == 'high' else 'normal',
            notification=messaging.AndroidNotification(
                sound='alarm_sound',
                channel_id='gift_alerts',
                priority='max' if priority == 'high' else 'high',
                default_sound=False,
                vibrate_timings=[0, 1000, 500, 1000] if priority == 'high' else [0, 500],
                visibility='public'
            ),
            data=data or {}
        )
        
        # Create messages for all tokens
        messages = []
        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=self._prepare_data(data),
                token=token,
                android=android_config
            )
            messages.append(message)
        
        try:
            # Send all messages in batch (max 500 per batch)
            batch_size = 500
            success_count = 0
            failure_count = 0
            
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                batch_response = messaging.send_all(batch)
                
                success_count += batch_response.success_count
                failure_count += batch_response.failure_count
                
                # Log failed tokens
                for idx, resp in enumerate(batch_response.responses):
                    if not resp.success:
                        logger.warning(f"Failed to send to token {tokens[i + idx]}: {resp.exception}")
            
            logger.info(f"Batch send complete. Success: {success_count}, Failure: {failure_count}")
            
            return {
                "success": success_count,
                "failure": failure_count
            }
            
        except Exception as e:
            logger.error(f"Error sending batch messages: {e}")
            return {
                "success": 0,
                "failure": len(tokens)
            }
    
    async def send_data_message(self, token: str, data: Dict) -> bool:
        """
        Send data-only message (no notification)
        
        Args:
            token: FCM token
            data: Data payload
            
        Returns:
            True if successful
        """
        if not self.initialized:
            return False
        
        try:
            message = messaging.Message(
                data=self._prepare_data(data),
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    data=data
                )
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent data message: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending data message: {e}")
            return False
    
    def _prepare_data(self, data: Optional[Dict]) -> Dict[str, str]:
        """
        Prepare data payload for FCM (all values must be strings)
        
        Args:
            data: Raw data dictionary
            
        Returns:
            Prepared data with string values
        """
        if not data:
            return {}
        
        prepared = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                prepared[key] = json.dumps(value)
            else:
                prepared[key] = str(value)
        
        # Add timestamp if not present
        if 'timestamp' not in prepared:
            prepared['timestamp'] = datetime.utcnow().isoformat()
        
        return prepared
    
    async def create_topic(self, topic_name: str) -> bool:
        """
        Create a topic for grouped notifications
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            True if successful
        """
        # Topics are created automatically when devices subscribe
        return True
    
    async def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict:
        """
        Subscribe tokens to a topic
        
        Args:
            tokens: List of FCM tokens
            topic: Topic name
            
        Returns:
            Results dictionary
        """
        if not self.initialized:
            return {"success": 0, "failure": len(tokens)}
        
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            
            return {
                "success": response.success_count,
                "failure": response.failure_count
            }
            
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return {"success": 0, "failure": len(tokens)}
    
    async def send_to_topic(self, topic: str, title: str, body: str,
                           data: Dict = None) -> bool:
        """
        Send notification to all devices subscribed to a topic
        
        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Additional data
            
        Returns:
            True if successful
        """
        if not self.initialized:
            return False
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=self._prepare_data(data),
                topic=topic
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent to topic {topic}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to topic: {e}")
            return False


# Singleton instance
_push_service = None

def get_push_service() -> PushNotificationService:
    """Get singleton push service instance"""
    global _push_service
    if _push_service is None:
        _push_service = PushNotificationService()
    return _push_service