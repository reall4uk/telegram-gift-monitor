#!/usr/bin/env python3
"""
Telegram Gift Monitor Service
Monitors specified Telegram channels for gift notifications
"""

import asyncio
import logging
import re
import os
from datetime import datetime
from typing import List, Dict, Optional
import redis.asyncio as redis
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import json

from gift_detector import GiftDetector
from push_notifications import PushNotificationService
from database_docker_adapter import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramMonitor:
    """Main monitoring service for Telegram channels"""
    
    def __init__(self, api_id: str, api_hash: str, phone: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.client = None
        self.gift_detector = GiftDetector()
        self.push_service = PushNotificationService()
        self.db = Database()
        self.redis = None
        self.monitored_channels = []
        
    async def initialize(self):
        """Initialize all connections and services"""
        try:
            # Initialize Pyrogram client
            self.client = Client(
                "gift_monitor_session",
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone_number=self.phone
            )
            
            # Initialize Redis for caching (optional)
            try:
                self.redis = redis.Redis(
                    host='localhost',
                    port=6379,
                    decode_responses=True
                )
                await self.redis.ping()
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis not available: {e}. Continuing without cache.")
                self.redis = None
            
            # Initialize database (optional)
            try:
                await self.db.initialize()
                # Load monitored channels from database
                self.monitored_channels = await self.db.get_active_channels()
                logger.info(f"Loaded {len(self.monitored_channels)} channels from database")
            except Exception as e:
                logger.warning(f"Database not available: {e}. Will use channels from .env")
                self.monitored_channels = []
            
            # Initialize push notification service
            try:
                await self.push_service.initialize()
                logger.info("Push notification service initialized")
            except Exception as e:
                logger.warning(f"Push notifications not available: {e}")
            
            logger.info("Monitor service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize monitor: {e}")
            raise
    
    def get_monitored_chat_ids(self):
        """Get list of chat IDs to monitor from channels list"""
        chat_ids = []
        for channel in self.monitored_channels:
            # Handle both @username and numeric IDs
            if 'username' in channel:
                chat_ids.append(channel['username'])
            if 'telegram_id' in channel:
                chat_ids.append(channel['telegram_id'])
        return chat_ids
    
    async def start(self):
        """Start monitoring channels"""
        async with self.client:
            logger.info("Telegram client connected")
            
            # Get current user info
            me = await self.client.get_me()
            logger.info(f"Logged in as: {me.first_name} (@{me.username})")
            
            # Load channels from config if no channels in DB
            if not self.monitored_channels:
                await self.load_channels_from_config()
            
            # Join channels if not already joined
            for channel in self.monitored_channels:
                try:
                    username = channel.get('username', '')
                    if username:
                        await self.client.join_chat(username)
                        logger.info(f"Joined channel: {username}")
                except FloodWait as e:
                    logger.warning(f"FloodWait: sleeping for {e.x} seconds")
                    await asyncio.sleep(e.x)
                except Exception as e:
                    logger.error(f"Failed to join {username}: {e}")
            
            # Set up message handler for specific channels
            @self.client.on_message(filters.chat(self.get_monitored_chat_ids()))
            async def message_handler(client, message: Message):
                await self.process_message(message)
            
            # DEBUG: Временный обработчик для отладки - видеть ВСЕ сообщения
            @self.client.on_message()
            async def debug_all_messages(client, message: Message):
                chat_name = message.chat.title or message.chat.username or str(message.chat.id)
                chat_username = message.chat.username or str(message.chat.id)
                text = (message.text or message.caption or "")[:100]
                logger.info(f"[DEBUG] Message from {chat_name} (@{chat_username}): {text}...")
                
                # Проверяем, должны ли мы мониторить этот чат
                if self._is_monitored_channel(chat_username):
                    logger.info(f"[DEBUG] ✅ This channel IS monitored")
                else:
                    logger.info(f"[DEBUG] ❌ This channel is NOT monitored")
            
            # Keep the client running
            logger.info("Monitor is running... Press Ctrl+C to stop")
            logger.info(f"Monitoring {len(self.monitored_channels)} channels")
            logger.info("Monitored channels list:")
            for ch in self.monitored_channels:
                logger.info(f"  - {ch['title']} (username: {ch['username']}, id: {ch['telegram_id']})")
            await asyncio.Event().wait()
    
    async def load_channels_from_config(self):
        """Load channels from environment config"""
        channels_str = os.getenv('MONITOR_CHANNELS', '')
        if not channels_str:
            logger.warning("No channels specified in MONITOR_CHANNELS")
            return
        
        channels = [ch.strip() for ch in channels_str.split(',')]
        logger.info(f"Loading {len(channels)} channels from config")
        
        for channel_username in channels:
            try:
                # Get channel info from Telegram
                chat = await self.client.get_chat(channel_username)
                
                # Add to local list (without database)
                channel_data = {
                    'telegram_id': chat.id,
                    'username': channel_username,
                    'title': chat.title or channel_username,
                    'keywords': []
                }
                self.monitored_channels.append(channel_data)
                
                logger.info(f"Added channel: {chat.title} ({channel_username})")
                
                # Try to save to database if available
                if self.db.pool:
                    try:
                        await self.db.add_channel(
                            channel_id=chat.id,
                            username=channel_username,
                            title=chat.title or channel_username,
                            keywords=[]
                        )
                    except Exception as e:
                        logger.warning(f"Could not save channel to database: {e}")
                
            except Exception as e:
                logger.error(f"Failed to add channel {channel_username}: {e}")
    
    async def process_message(self, message: Message):
        """Process incoming channel message"""
        try:
            # Check if message is from monitored channel
            channel_username = message.chat.username or str(message.chat.id)
            
            # Логируем для отладки
            logger.info(f"[PROCESS] Checking message from: {channel_username}")
            
            if not self._is_monitored_channel(channel_username):
                logger.info(f"[PROCESS] Channel {channel_username} not in monitored list, skipping")
                return
            
            # Check for duplicate (deduplication) if Redis available
            if self.redis:
                message_key = f"msg:{message.chat.id}:{message.id}"
                try:
                    exists = await self.redis.exists(message_key)
                    if exists:
                        return
                    # Mark as processed (expire after 1 hour)
                    await self.redis.setex(message_key, 3600, "1")
                except Exception as e:
                    logger.warning(f"Redis error: {e}")
            
            # Extract text content
            text = message.text or message.caption or ""
            logger.info(f"[PROCESS] Message text: {text[:100]}...")
            
            # Detect if it's a gift notification
            gift_data = self.gift_detector.detect_gift(text)
            
            if gift_data:
                logger.info(f"🎁 Gift detected in {channel_username}: {gift_data['id']}")
                logger.info(f"Price: {gift_data.get('price', 'Unknown')}")
                logger.info(f"Link: https://t.me/{channel_username}/{message.id}")
                
                # Save to database if available
                if self.db.pool:
                    try:
                        notification_id = await self.db.save_notification(
                            channel_id=message.chat.id,
                            channel_username=channel_username,
                            message_text=text,
                            gift_data=gift_data,
                            message_link=f"https://t.me/{channel_username}/{message.id}"
                        )
                        
                        # Send push notifications
                        await self._send_notifications(
                            channel_username=channel_username,
                            gift_data=gift_data,
                            notification_id=notification_id
                        )
                        
                        # Update statistics
                        await self._update_statistics(channel_username, gift_data)
                    except Exception as e:
                        logger.error(f"Database error: {e}")
                else:
                    logger.info("📱 [Would send push notification if database was connected]")
            else:
                logger.info(f"[PROCESS] No gift keywords found in message")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _is_monitored_channel(self, channel_username: str) -> bool:
        """Check if channel is in monitored list"""
        # Нормализуем username для сравнения
        normalized_username = channel_username.replace('@', '')
        
        for ch in self.monitored_channels:
            ch_username = ch.get('username', '').replace('@', '')
            ch_id = str(ch.get('telegram_id', ''))
            
            # Проверяем и по username, и по ID
            if ch_username == normalized_username or ch_id == channel_username:
                return True
                
        return False
    
    async def _send_notifications(self, channel_username: str, 
                                  gift_data: Dict, notification_id: int):
        """Send push notifications to all eligible users"""
        try:
            # Get all active users with valid licenses
            active_users = await self.db.get_active_users_for_channel(channel_username)
            
            if not active_users:
                logger.warning(f"No active users for channel {channel_username}")
                return
            
            # Prepare notification data
            notification_data = {
                'id': notification_id,
                'channel': channel_username,
                'gift_id': gift_data['id'],
                'gift_name': gift_data.get('name', 'Limited Gift'),
                'price': gift_data.get('price', 'Unknown'),
                'availability': gift_data.get('availability', 'Unknown'),
                'priority': 'high',
                'sound': 'alarm_loud',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Send to each user
            success_count = 0
            for user in active_users:
                try:
                    # Check user preferences
                    if user.get('is_muted'):
                        continue
                    
                    # Get user's FCM tokens
                    tokens = await self.db.get_user_fcm_tokens(user['id'])
                    
                    if tokens:
                        results = await self.push_service.send_to_tokens(
                            tokens=tokens,
                            title=f"🎁 New Gift Alert!",
                            body=f"Gift {gift_data['id']} available for {gift_data.get('price', 'Unknown')}",
                            data=notification_data,
                            priority='high'
                        )
                        
                        if results['success'] > 0:
                            success_count += 1
                            
                            # Log delivery
                            await self.db.log_notification_delivery(
                                notification_id=notification_id,
                                user_id=user['id'],
                                delivered=True
                            )
                        
                except Exception as e:
                    logger.error(f"Failed to send to user {user['id']}: {e}")
            
            logger.info(f"Sent notifications to {success_count}/{len(active_users)} users")
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}", exc_info=True)
    
    async def _update_statistics(self, channel_username: str, gift_data: Dict):
        """Update channel and gift statistics"""
        try:
            # Update channel stats
            await self.db.increment_channel_stats(
                channel_username=channel_username,
                gift_count=1
            )
            
            # Update gift price history
            if gift_data.get('price'):
                await self.db.add_gift_price_history(
                    gift_id=gift_data['id'],
                    price=gift_data['price'],
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
    
    async def add_channel(self, channel_username: str, keywords: List[str] = None):
        """Add new channel to monitoring list"""
        try:
            # Normalize username
            if not channel_username.startswith('@'):
                channel_username = f"@{channel_username}"
            
            # Check if already monitoring
            if self._is_monitored_channel(channel_username):
                return {"success": False, "error": "Channel already monitored"}
            
            # Try to join channel
            try:
                chat = await self.client.join_chat(channel_username)
                channel_id = chat.id
                channel_title = chat.title
            except Exception as e:
                return {"success": False, "error": f"Failed to join channel: {e}"}
            
            # Save to database
            await self.db.add_channel(
                channel_id=channel_id,
                username=channel_username,
                title=channel_title,
                keywords=keywords or []
            )
            
            # Update local cache
            self.monitored_channels = await self.db.get_active_channels()
            
            return {"success": True, "channel_id": channel_id}
            
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_channel(self, channel_username: str):
        """Remove channel from monitoring"""
        try:
            await self.db.deactivate_channel(channel_username)
            self.monitored_channels = await self.db.get_active_channels()
            
            # Leave channel
            try:
                await self.client.leave_chat(channel_username)
            except:
                pass
                
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error removing channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.redis:
                await self.redis.close()
            
            if self.db:
                await self.db.close()
                
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main entry point"""
    import os
    from dotenv import load_dotenv
    
    # Загружаем .env из корня проекта
    # Получаем путь к текущему файлу
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Поднимаемся на 3 уровня вверх до корня проекта
    root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    env_path = os.path.join(root_dir, '.env')
    
    # Загружаем .env файл
    load_dotenv(env_path)
    
    # Проверяем, что переменные загружены
    if not os.getenv('TELEGRAM_API_ID'):
        logger.error(f"Failed to load .env from {env_path}")
        logger.error("Make sure .env file exists in C:\\telegram-gift-monitor\\")
        return
    
    monitor = TelegramMonitor(
        api_id=os.getenv('TELEGRAM_API_ID'),
        api_hash=os.getenv('TELEGRAM_API_HASH'),
        phone=os.getenv('TELEGRAM_PHONE')
    )
    
    try:
        await monitor.initialize()
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await monitor.cleanup()


if __name__ == "__main__":
    asyncio.run(main())