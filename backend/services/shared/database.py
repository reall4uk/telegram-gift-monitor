#!/usr/bin/env python3
"""
Database Module
Handles all database operations using asyncpg
"""

import asyncpg
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class Database:
    """Async database operations handler"""
    
    def __init__(self, connection_url: str = None):
        self.connection_url = connection_url or os.getenv('DATABASE_URL')
        # Если не нашли в окружении, попробуем загрузить .env
        if not self.connection_url:
            from dotenv import load_dotenv
            # Пробуем загрузить из корня проекта
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
            env_path = os.path.join(root_dir, '.env')
            load_dotenv(env_path)
            self.connection_url = os.getenv('DATABASE_URL')
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            # Для Windows используем специальные настройки
            self.pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=1,
                max_size=5,
                command_timeout=60,
                # Настройки для Windows
                server_settings={
                    'jit': 'off'
                },
                # Дополнительные параметры для стабильности
                setup=self._setup_connection,
                init=self._init_connection
            )
            logger.info("Database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            # Пробуем альтернативные способы подключения для Windows
            if "connection was closed" in str(e):
                logger.info("Trying alternative connection method for Windows...")
                try:
                    # Пробуем с другими параметрами
                    self.pool = await asyncpg.create_pool(
                        self.connection_url.replace('localhost', '127.0.0.1'),
                        min_size=1,
                        max_size=2,
                        max_inactive_connection_lifetime=5
                    )
                    logger.info("Database pool initialized with alternative settings")
                except Exception as e2:
                    logger.error(f"Alternative connection also failed: {e2}")
                    raise
            else:
                raise
    
    async def _setup_connection(self, connection):
        """Setup connection parameters"""
        await connection.execute("SET jit = 'off'")
    
    async def _init_connection(self, connection):
        """Initialize connection"""
        await connection.execute("SELECT 1")
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire database connection from pool"""
        async with self.pool.acquire() as connection:
            yield connection
    
    # User operations
    async def create_user(self, telegram_id: int, telegram_username: str = None,
                         device_id: str = None, device_type: str = None) -> str:
        """Create new user"""
        async with self.acquire() as conn:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (telegram_id, telegram_username)
                VALUES ($1, $2)
                ON CONFLICT (telegram_id) DO UPDATE
                SET telegram_username = EXCLUDED.telegram_username,
                    last_active_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                telegram_id, telegram_username
            )
            
            # Add device if provided
            if device_id and device_type:
                await conn.execute(
                    """
                    INSERT INTO user_devices (user_id, device_id, device_type)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, device_id) DO UPDATE
                    SET last_seen_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                    """,
                    user_id, device_id, device_type
                )
            
            return str(user_id)
    
    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.*, 
                       l.license_type,
                       l.expires_at as license_expires_at,
                       CASE WHEN l.expires_at > CURRENT_TIMESTAMP THEN TRUE ELSE FALSE END as has_valid_license
                FROM users u
                LEFT JOIN licenses l ON u.id = l.user_id 
                    AND l.revoked_at IS NULL 
                    AND l.expires_at > CURRENT_TIMESTAMP
                WHERE u.id = $1
                """,
                user_id
            )
            return dict(row) if row else None
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID"""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id
            )
            return dict(row) if row else None
    
    async def update_user_device(self, user_id: str, device_id: str, 
                                device_type: str, fcm_token: str):
        """Update user device information"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_devices (user_id, device_id, device_type, fcm_token)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, device_id) DO UPDATE
                SET device_type = EXCLUDED.device_type,
                    fcm_token = EXCLUDED.fcm_token,
                    last_seen_at = CURRENT_TIMESTAMP,
                    is_active = TRUE
                """,
                user_id, device_id, device_type, fcm_token
            )
    
    # License operations
    async def create_license(self, license_key: str, license_type: str,
                           max_channels: int, max_devices: int, duration_days: int) -> str:
        """Create new license"""
        async with self.acquire() as conn:
            license_id = await conn.fetchval(
                """
                INSERT INTO licenses (
                    license_key, license_type, max_channels, 
                    max_devices, duration_days
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                license_key, license_type, max_channels, max_devices, duration_days
            )
            return str(license_id)
    
    async def get_license(self, license_key: str) -> Optional[Dict]:
        """Get license by key"""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM licenses WHERE license_key = $1",
                license_key
            )
            return dict(row) if row else None
    
    async def activate_license(self, license_key: str, user_id: str,
                             device_id: str, expires_at: datetime) -> Dict:
        """Activate license for user"""
        async with self.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE licenses 
                    SET user_id = $2,
                        activated_at = CURRENT_TIMESTAMP,
                        expires_at = $3,
                        activation_device_id = $4
                    WHERE license_key = $1
                        AND user_id IS NULL
                        AND revoked_at IS NULL
                    """,
                    license_key, user_id, expires_at, device_id
                )
                
                # Update user's license status
                await conn.execute(
                    """
                    UPDATE users 
                    SET has_valid_license = TRUE 
                    WHERE id = $1
                    """,
                    user_id
                )
                
                return {"success": True}
            except Exception as e:
                logger.error(f"License activation error: {e}")
                return {"success": False, "error": str(e)}
    
    async def get_user_license(self, user_id: str) -> Optional[Dict]:
        """Get user's active license"""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *,
                       CASE WHEN expires_at > CURRENT_TIMESTAMP THEN TRUE ELSE FALSE END as is_valid,
                       (SELECT COUNT(*) FROM user_devices WHERE user_id = $1 AND is_active = TRUE) as devices_count
                FROM licenses 
                WHERE user_id = $1 
                    AND revoked_at IS NULL
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                user_id
            )
            return dict(row) if row else None
    
    # Channel operations
    async def get_active_channels(self) -> List[Dict]:
        """Get all active channels"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, telegram_id, username, title, keywords
                FROM channels 
                WHERE is_active = TRUE
                """
            )
            return [dict(row) for row in rows]
    
    async def get_available_channels(self) -> List[Dict]:
        """Get all available channels for subscription"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, username, title, description, 
                       subscriber_count, total_gifts_detected
                FROM channels 
                WHERE is_active = TRUE
                ORDER BY subscriber_count DESC
                """
            )
            return [dict(row) for row in rows]
    
    async def get_channel_by_username(self, username: str) -> Optional[Dict]:
        """Get channel by username"""
        async with self.acquire() as conn:
            # Normalize username
            if not username.startswith('@'):
                username = f"@{username}"
            
            row = await conn.fetchrow(
                "SELECT * FROM channels WHERE username = $1",
                username
            )
            return dict(row) if row else None
    
    async def add_channel(self, channel_id: int, username: str,
                         title: str, keywords: List[str] = None):
        """Add new channel"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO channels (telegram_id, username, title, keywords)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = EXCLUDED.username,
                    title = EXCLUDED.title,
                    keywords = EXCLUDED.keywords,
                    is_active = TRUE
                """,
                channel_id, username, title, keywords or []
            )
    
    # Subscription operations
    async def subscribe_user_to_channel(self, user_id: str, channel_id: str,
                                       settings: Dict = None) -> Dict:
        """Subscribe user to channel"""
        async with self.acquire() as conn:
            sub_id = await conn.fetchval(
                """
                INSERT INTO user_subscriptions (user_id, channel_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, channel_id) DO UPDATE
                SET is_muted = FALSE,
                    muted_until = NULL
                RETURNING id
                """,
                user_id, channel_id
            )
            
            # Update settings if provided
            if settings:
                await self._update_subscription_settings(conn, sub_id, settings)
            
            return {"id": str(sub_id)}
    
    async def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """Get user's channel subscriptions"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.*, c.username, c.title, c.total_gifts_detected
                FROM user_subscriptions s
                JOIN channels c ON s.channel_id = c.id
                WHERE s.user_id = $1
                ORDER BY s.subscribed_at DESC
                """,
                user_id
            )
            return [dict(row) for row in rows]
    
    async def get_user_subscriptions_count(self, user_id: str) -> int:
        """Get count of user's subscriptions"""
        async with self.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_subscriptions WHERE user_id = $1",
                user_id
            )
            return count
    
    # Notification operations
    async def save_notification(self, channel_id: int, channel_username: str,
                              message_text: str, gift_data: Dict,
                              message_link: str) -> int:
        """Save notification to database"""
        async with self.acquire() as conn:
            # Get channel UUID
            channel_uuid = await conn.fetchval(
                "SELECT id FROM channels WHERE telegram_id = $1",
                channel_id
            )
            
            if not channel_uuid:
                # Create channel if not exists
                channel_uuid = await conn.fetchval(
                    """
                    INSERT INTO channels (telegram_id, username, title)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    channel_id, channel_username, channel_username
                )
            
            # Save notification
            notification_id = await conn.fetchval(
                """
                INSERT INTO notifications (
                    channel_id, message_text, gift_id, 
                    gift_data, message_link
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                channel_uuid, message_text, gift_data.get('id'),
                json.dumps(gift_data), message_link
            )
            
            # Update channel stats
            await conn.execute(
                """
                UPDATE channels 
                SET total_gifts_detected = total_gifts_detected + 1,
                    last_checked_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                channel_uuid
            )
            
            return notification_id
    
    async def get_active_users_for_channel(self, channel_username: str) -> List[Dict]:
        """Get all active users subscribed to a channel"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT u.id, u.telegram_id, s.is_muted, s.notification_sound
                FROM users u
                JOIN user_subscriptions s ON u.id = s.user_id
                JOIN channels c ON s.channel_id = c.id
                WHERE c.username = $1
                    AND u.has_valid_license = TRUE
                    AND u.is_banned = FALSE
                    AND s.is_muted = FALSE
                """,
                channel_username
            )
            return [dict(row) for row in rows]
    
    async def get_user_fcm_tokens(self, user_id: str) -> List[str]:
        """Get user's active FCM tokens"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT fcm_token 
                FROM user_devices 
                WHERE user_id = $1 
                    AND is_active = TRUE 
                    AND fcm_token IS NOT NULL
                """,
                user_id
            )
            return [row['fcm_token'] for row in rows]
    
    # Statistics operations
    async def get_system_stats(self) -> Dict:
        """Get system statistics"""
        async with self.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    (SELECT COUNT(*) FROM users) as total_users,
                    (SELECT COUNT(*) FROM users WHERE has_valid_license = TRUE) as licensed_users,
                    (SELECT COUNT(*) FROM channels WHERE is_active = TRUE) as active_channels,
                    (SELECT COUNT(*) FROM notifications WHERE created_at > CURRENT_DATE) as today_notifications,
                    (SELECT COUNT(*) FROM licenses WHERE activated_at > CURRENT_DATE) as today_activations
                """
            )
            return dict(stats)
    
    # Дополнительные методы для полной функциональности
    async def update_user_license_status(self, user_id: str, has_valid_license: bool):
        """Update user's license status"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE users 
                SET has_valid_license = $2 
                WHERE id = $1
                """,
                user_id, has_valid_license
            )
    
    async def deactivate_channel(self, channel_username: str):
        """Deactivate channel"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE channels 
                SET is_active = FALSE 
                WHERE username = $1
                """,
                channel_username
            )
    
    async def unsubscribe_user_from_channel(self, user_id: str, channel_id: int) -> Dict:
        """Unsubscribe user from channel"""
        async with self.acquire() as conn:
            affected = await conn.execute(
                """
                DELETE FROM user_subscriptions 
                WHERE user_id = $1 AND channel_id = (
                    SELECT id FROM channels WHERE telegram_id = $2
                )
                """,
                user_id, channel_id
            )
            return {"success": affected != "DELETE 0"}
    
    async def get_user_notifications(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get user's notification history"""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT n.*, c.username as channel_username, c.title as channel_title
                FROM notifications n
                JOIN channels c ON n.channel_id = c.id
                JOIN user_subscriptions s ON s.channel_id = c.id
                WHERE s.user_id = $1
                ORDER BY n.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset
            )
            return [dict(row) for row in rows]
    
    async def save_fcm_token(self, user_id: str, token: str, device_id: str):
        """Save FCM token for user device"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_devices 
                SET fcm_token = $2 
                WHERE user_id = $1 AND device_id = $3
                """,
                user_id, token, device_id
            )
    
    async def update_fcm_token(self, user_id: str, device_id: str, new_token: str):
        """Update FCM token for device"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_devices 
                SET fcm_token = $3, last_seen_at = CURRENT_TIMESTAMP
                WHERE user_id = $1 AND device_id = $2
                """,
                user_id, device_id, new_token
            )
    
    async def get_user_settings(self, user_id: str) -> Optional[Dict]:
        """Get user settings"""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_settings WHERE user_id = $1",
                user_id
            )
            return dict(row) if row else None
    
    async def update_user_settings(self, user_id: str, settings: Dict):
        """Update user settings"""
        async with self.acquire() as conn:
            # Подготавливаем поля для обновления
            fields = []
            values = [user_id]
            param_count = 1
            
            for key, value in settings.items():
                param_count += 1
                fields.append(f"{key} = ${param_count}")
                values.append(value)
            
            if fields:
                query = f"""
                    INSERT INTO user_settings (user_id, {', '.join(settings.keys())})
                    VALUES ($1, {', '.join(f'${i+2}' for i in range(len(settings)))})
                    ON CONFLICT (user_id) DO UPDATE
                    SET {', '.join(fields)}
                """
                await conn.execute(query, *values)
    
    async def get_user_devices_count(self, user_id: str) -> int:
        """Get count of user's active devices"""
        async with self.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM user_devices 
                WHERE user_id = $1 AND is_active = TRUE
                """,
                user_id
            )
            return count
    
    async def revoke_license(self, license_key: str, reason: str) -> Dict:
        """Revoke license"""
        async with self.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE licenses 
                    SET revoked_at = CURRENT_TIMESTAMP,
                        revoke_reason = $2
                    WHERE license_key = $1
                    """,
                    license_key, reason
                )
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def increment_channel_stats(self, channel_username: str, gift_count: int):
        """Update channel statistics"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE channels 
                SET total_gifts_detected = total_gifts_detected + $2,
                    last_checked_at = CURRENT_TIMESTAMP
                WHERE username = $1
                """,
                channel_username, gift_count
            )
    
    async def add_gift_price_history(self, gift_id: str, price: str, timestamp: datetime):
        """Add gift price history record"""
        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gift_price_history (gift_id, price, detected_at)
                VALUES ($1, $2, $3)
                """,
                gift_id, price, timestamp
            )
    
    async def log_notification_delivery(self, notification_id: int, user_id: str, delivered: bool):
        """Log notification delivery status"""
        async with self.acquire() as conn:
            # Получаем device_id пользователя
            device_id = await conn.fetchval(
                """
                SELECT id FROM user_devices 
                WHERE user_id = $1 AND is_active = TRUE 
                LIMIT 1
                """,
                user_id
            )
            
            if device_id:
                await conn.execute(
                    """
                    INSERT INTO notification_deliveries 
                    (notification_id, user_id, device_id, delivered, delivered_at)
                    VALUES ($1, $2, $3, $4, CASE WHEN $4 THEN CURRENT_TIMESTAMP ELSE NULL END)
                    """,
                    notification_id, user_id, device_id, delivered
                )