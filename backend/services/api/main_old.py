#!/usr/bin/env python3
"""
Main API Server for Telegram Gift Monitor
Handles authentication, licenses, and client communication
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import jwt
import secrets
import hashlib
from pydantic import BaseModel, Field

from database_docker_adapter import Database
from auth import AuthService
from licenses import LicenseService
from push_notifications import PushNotificationService
from secure_config_api import router as secure_config_router  # ДОБАВЛЕНО

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
db = Database()
auth_service = AuthService()
license_service = LicenseService()
push_service = PushNotificationService()


# Pydantic models
class UserRegister(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None
    device_id: str
    device_type: str = Field(pattern="^(android|ios)$")
    fcm_token: str


class LicenseActivate(BaseModel):
    license_key: str
    device_id: str


class ChannelSubscribe(BaseModel):
    channel_username: str
    notification_settings: Optional[Dict] = None


class NotificationTest(BaseModel):
    title: str = "Test Notification"
    body: str = "This is a test notification"
    sound: str = "default"


class UpdateFCMToken(BaseModel):
    fcm_token: str
    device_id: str


# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up API server...")
    await db.initialize()
    await push_service.initialize()
    yield
    # Shutdown
    logger.info("Shutting down API server...")
    await db.close()


# Create FastAPI app
app = FastAPI(
    title="Telegram Gift Monitor API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Подключаем роутер secure_config_api  # ДОБАВЛЕНО
app.include_router(secure_config_router, tags=["security"])


# JWT token verification
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user data"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, 
            auth_service.SECRET_KEY, 
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Verify user exists and has valid license
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.get("has_valid_license"):
            raise HTTPException(status_code=403, detail="No valid license")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Rate limiting decorator
from functools import wraps
import time

rate_limit_storage = {}

def rate_limit(max_calls: int, time_window: int):
    """Simple rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host
            now = time.time()
            
            # Clean old entries
            rate_limit_storage[client_ip] = [
                timestamp for timestamp in rate_limit_storage.get(client_ip, [])
                if now - timestamp < time_window
            ]
            
            # Check rate limit
            if len(rate_limit_storage.get(client_ip, [])) >= max_calls:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            # Add current call
            if client_ip not in rate_limit_storage:
                rate_limit_storage[client_ip] = []
            rate_limit_storage[client_ip].append(now)
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Telegram Gift Monitor API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/gifts/recent")
async def get_recent_gifts(limit: int = 50):
    """Get recent gift notifications without authentication for testing"""
    try:
        logger.info(f"Getting recent gifts, limit: {limit}")
        
        # Получаем последние уведомления из БД через Docker
        query = """
            SELECT 
                n.id,
                n.gift_id,
                n.gift_data,
                n.message_link,
                n.created_at,
                c.username as channel_username
            FROM notifications n
            JOIN channels c ON n.channel_id = c.id
            ORDER BY n.created_at DESC
            LIMIT %s
        """
        
        result = await db.execute_query(query, [limit])
        logger.info(f"Query result type: {type(result)}, length: {len(result) if result else 0}")
        
        if result and len(result) > 0:
            # execute_query уже возвращает список словарей
            gifts = []
            for row in result:
                try:
                    # row уже является словарем с нужными полями
                    gift_data = row.get('gift_data', {})
                    
                    # Добавляем поле name если его нет
                    if 'name' not in gift_data:
                        gift_data['name'] = f"Gift #{gift_data.get('id', 'unknown')[:8]}"
                    
                    gifts.append({
                        "id": row.get('gift_id', row.get('id')),
                        "gift_id": row.get('gift_id'),
                        "gift_data": gift_data,
                        "channel_username": f"@{row.get('channel_username', '').lstrip('@')}",
                        "message_link": row.get('message_link'),
                        "created_at": row.get('created_at')
                    })
                    logger.info(f"Processed gift: {gift_data.get('id')}")
                except Exception as e:
                    logger.error(f"Error processing row: {e}, row: {row}")
            
            if gifts:
                logger.info(f"Returning {len(gifts)} gifts from database")
                return gifts
        
        logger.info("No gifts found in database, returning test data")
        # Если нет данных из БД, возвращаем тестовые
        return [
            {
                "id": "5902339509239940491",
                "gift_id": "5902339509239940491",
                "gift_data": {
                    "id": "5902339509239940491",
                    "name": "Gift from Database",
                    "price": "5,000",
                    "total": 10000,
                    "available": 250,
                    "available_percent": 2.5,
                    "is_limited": True,
                    "is_sold_out": False,
                    "emoji": "🎁",
                    "urgency_score": 0.8
                },
                "channel_username": "@News_Collections",
                "message_link": "https://t.me/News_Collections/306",
                "created_at": datetime.utcnow().isoformat()
            }
        ]
        
    except Exception as e:
        logger.error(f"Error getting recent gifts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # В случае ошибки возвращаем тестовые данные
        return [
            {
                "id": "test123",
                "gift_id": "test123",
                "gift_data": {
                    "id": "test123",
                    "name": "Test Gift",
                    "price": "1,000",
                    "total": 100,
                    "available": 10,
                    "available_percent": 10.0,
                    "is_limited": True,
                    "is_sold_out": False,
                    "emoji": "🎁",
                    "urgency_score": 0.5
                },
                "channel_username": "@test_channel",
                "message_link": "https://t.me/test_channel/1",
                "created_at": datetime.utcnow().isoformat()
            }
        ]


@app.post("/api/v1/auth/register")
@rate_limit(max_calls=5, time_window=300)  # 5 calls per 5 minutes
async def register(request: Request, user_data: UserRegister):
    """Register new user"""
    try:
        # Check if user already exists
        existing_user = await db.get_user_by_telegram_id(user_data.telegram_id)
        
        if existing_user:
            # Update FCM token and device info
            await db.update_user_device(
                user_id=existing_user["id"],
                device_id=user_data.device_id,
                device_type=user_data.device_type,
                fcm_token=user_data.fcm_token
            )
            user_id = existing_user["id"]
        else:
            # Create new user
            user_id = await db.create_user(
                telegram_id=user_data.telegram_id,
                telegram_username=user_data.telegram_username,
                device_id=user_data.device_id,
                device_type=user_data.device_type
            )
            
            # Save FCM token
            await db.save_fcm_token(
                user_id=user_id,
                token=user_data.fcm_token,
                device_id=user_data.device_id
            )
        
        # Generate JWT token
        token = auth_service.create_token(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "token": token,
            "has_valid_license": existing_user.get("has_valid_license", False) if existing_user else False
        }
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/v1/license/activate")
async def activate_license(
    license_data: LicenseActivate,
    user: dict = Depends(verify_token)
):
    """Activate license key"""
    try:
        # Verify license key
        license_info = await license_service.verify_license(license_data.license_key)
        
        if not license_info["valid"]:
            raise HTTPException(status_code=400, detail=license_info["error"])
        
        # Check if license already used
        if license_info.get("user_id") and license_info["user_id"] != user["id"]:
            raise HTTPException(status_code=400, detail="License already activated by another user")
        
        # Activate license for user
        result = await license_service.activate_license(
            license_key=license_data.license_key,
            user_id=user["id"],
            device_id=license_data.device_id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "expires_at": result["expires_at"],
            "license_type": result["license_type"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"License activation error: {e}")
        raise HTTPException(status_code=500, detail="Activation failed")


@app.get("/api/v1/license/status")
async def get_license_status(user: dict = Depends(verify_token)):
    """Get current license status"""
    try:
        license_info = await db.get_user_license(user["id"])
        
        if not license_info:
            return {
                "has_valid_license": False,
                "license_type": None,
                "expires_at": None
            }
        
        return {
            "has_valid_license": license_info["is_valid"],
            "license_type": license_info["license_type"],
            "expires_at": license_info["expires_at"],
            "devices_count": license_info["devices_count"],
            "max_devices": license_info["max_devices"]
        }
        
    except Exception as e:
        logger.error(f"License status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get license status")


@app.get("/api/v1/channels")
async def get_channels(user: dict = Depends(verify_token)):
    """Get list of available channels to monitor"""
    try:
        channels = await db.get_available_channels()
        user_subscriptions = await db.get_user_subscriptions(user["id"])
        
        # Mark subscribed channels
        subscription_ids = {sub["channel_id"] for sub in user_subscriptions}
        
        for channel in channels:
            channel["is_subscribed"] = channel["id"] in subscription_ids
        
        return {
            "success": True,
            "channels": channels,
            "subscribed_count": len(subscription_ids)
        }
        
    except Exception as e:
        logger.error(f"Get channels error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get channels")


@app.post("/api/v1/channels/subscribe")
async def subscribe_channel(
    subscription: ChannelSubscribe,
    user: dict = Depends(verify_token)
):
    """Subscribe to channel notifications"""
    try:
        # Verify channel exists
        channel = await db.get_channel_by_username(subscription.channel_username)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        # Check subscription limits based on license
        current_subs = await db.get_user_subscriptions_count(user["id"])
        max_channels = 1 if user.get("license_type") == "basic" else 100
        
        if current_subs >= max_channels:
            raise HTTPException(
                status_code=403, 
                detail=f"Subscription limit reached ({max_channels} channels)"
            )
        
        # Subscribe
        result = await db.subscribe_user_to_channel(
            user_id=user["id"],
            channel_id=channel["id"],
            settings=subscription.notification_settings
        )
        
        return {
            "success": True,
            "channel_id": channel["id"],
            "subscription_id": result["id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        raise HTTPException(status_code=500, detail="Subscription failed")


@app.delete("/api/v1/channels/{channel_id}/unsubscribe")
async def unsubscribe_channel(
    channel_id: int,
    user: dict = Depends(verify_token)
):
    """Unsubscribe from channel"""
    try:
        result = await db.unsubscribe_user_from_channel(user["id"], channel_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail="Not subscribed to this channel")
        
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail="Unsubscribe failed")


@app.get("/api/v1/notifications/history")
async def get_notification_history(
    user: dict = Depends(verify_token),
    limit: int = 50,
    offset: int = 0
):
    """Get user's notification history"""
    try:
        notifications = await db.get_user_notifications(
            user_id=user["id"],
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "notifications": notifications,
            "count": len(notifications)
        }
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notifications")


@app.post("/api/v1/notifications/test")
async def send_test_notification(
    test_data: NotificationTest,
    user: dict = Depends(verify_token)
):
    """Send test notification to user's devices"""
    try:
        # Get user's FCM tokens
        tokens = await db.get_user_fcm_tokens(user["id"])
        
        if not tokens:
            raise HTTPException(status_code=400, detail="No registered devices")
        
        # Send test notification
        results = await push_service.send_to_tokens(
            tokens=tokens,
            title=test_data.title,
            body=test_data.body,
            data={
                "type": "test",
                "timestamp": datetime.utcnow().isoformat(),
                "sound": test_data.sound
            },
            priority="high"
        )
        
        return {
            "success": True,
            "sent_to": results["success"],
            "failed": results["failure"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test notification error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send test notification")


@app.put("/api/v1/device/fcm-token")
async def update_fcm_token(
    token_data: UpdateFCMToken,
    user: dict = Depends(verify_token)
):
    """Update FCM token for device"""
    try:
        await db.update_fcm_token(
            user_id=user["id"],
            device_id=token_data.device_id,
            new_token=token_data.fcm_token
        )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Update FCM token error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update token")


@app.get("/api/v1/settings")
async def get_user_settings(user: dict = Depends(verify_token)):
    """Get user settings"""
    try:
        settings = await db.get_user_settings(user["id"])
        
        return {
            "success": True,
            "settings": settings or {
                "sound_enabled": True,
                "vibration_enabled": True,
                "led_enabled": True,
                "quiet_hours_enabled": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "notification_sound": "alarm_loud",
                "repeat_count": 3
            }
        }
        
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")


@app.put("/api/v1/settings")
async def update_user_settings(
    settings: Dict,
    user: dict = Depends(verify_token)
):
    """Update user settings"""
    try:
        await db.update_user_settings(user["id"], settings)
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


# Admin endpoints (protected)
@app.get("/api/v1/admin/stats", dependencies=[Depends(verify_token)])
async def get_admin_stats(
    admin_key: str = Header(...),
):
    """Get system statistics (admin only)"""
    if admin_key != "your-secret-admin-key":  # Change in production
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    try:
        stats = await db.get_system_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )