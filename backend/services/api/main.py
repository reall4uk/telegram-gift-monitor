#!/usr/bin/env python3
"""
Main API Server for Telegram Gift Monitor
Production version - works without Docker
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
import asyncpg
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules - исправленные импорты без Docker
from auth import router as auth_router, verify_token, create_access_token
from secure_config_api import router as secure_config_router
from config_endpoint import router as config_router
from licenses import router as licenses_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security
security = HTTPBearer()

# Simple Database Adapter для production без Docker
class DatabaseAdapter:
    """Простой адаптер для работы с PostgreSQL без Docker"""
    def __init__(self):
        self.pool = None
        self.connection_string = os.getenv(
            'DATABASE_URL',
            'postgresql://appuser:securepass123@localhost/telegram_gift_monitor'
        )
    
    async def initialize(self):
        """Initialize database connection"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connected successfully")
            await self._create_tables()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            # Продолжаем работу без БД
    
    async def _create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.pool:
            return
            
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                telegram_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT true
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                license_key VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id),
                device_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT true
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS monitoring_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                gifts_found INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT true
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                notifications_enabled BOOLEAN DEFAULT true,
                monitor_interval INTEGER DEFAULT 300,
                target_games TEXT[] DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for query in queries:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query)
            except Exception as e:
                logger.error(f"Failed to create table: {e}")
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
    
    async def execute(self, query: str, *args):
        """Execute a query"""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            return None
    
    async def fetchone(self, query: str, *args):
        """Fetch one row"""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        except Exception as e:
            logger.error(f"Database fetchone error: {e}")
            return None
    
    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)
        except Exception as e:
            logger.error(f"Database fetch error: {e}")
            return []

# Simple Push Service
class PushService:
    """Простой сервис для push-уведомлений"""
    def __init__(self):
        self.initialized = False
    
    async def initialize(self):
        """Initialize push service"""
        # TODO: Добавить Firebase когда будут ключи
        logger.info("Push service initialized (mock mode)")
        self.initialized = True
    
    async def send_notification(self, user_id: int, title: str, body: str):
        """Send push notification"""
        if not self.initialized:
            return False
        # TODO: Реализовать отправку через Firebase
        logger.info(f"Mock notification sent to user {user_id}: {title}")
        return True

# Global services
db = DatabaseAdapter()
push_service = PushService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    try:
        # Initialize database
        logger.info("Initializing services...")
        await db.initialize()
        await push_service.initialize()
        
        logger.info("All services initialized successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Продолжаем работу даже если что-то не инициализировалось
        yield
    finally:
        logger.info("Shutting down services...")
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(secure_config_router, prefix="/api/v1", tags=["secure-config"])
app.include_router(config_router, prefix="/config", tags=["config"])
app.include_router(licenses_router, prefix="/licenses", tags=["licenses"])

# Models
class MonitoringStatus(BaseModel):
    user_id: int
    is_active: bool
    gifts_found: int
    last_check: Optional[datetime]

class UserSettings(BaseModel):
    notifications_enabled: bool
    monitor_interval: int
    target_games: List[str]

class StartMonitoringRequest(BaseModel):
    target_games: List[str] = ["Hamster Kombat", "Major", "Tomarket"]
    interval: int = 300

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Telegram Gift Monitor API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "auth": "/auth",
            "api": "/api/v1",
            "config": "/config",
            "licenses": "/licenses",
            "docs": "/docs"
        }
    }

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = "operational" if db.pool else "degraded"
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "operational",
            "database": db_status,
            "push_notifications": "operational" if push_service.initialized else "degraded"
        }
    }

# API v1 endpoints
@app.get("/api/v1/monitoring/status", response_model=MonitoringStatus)
async def get_monitoring_status(current_user: dict = Depends(verify_token)):
    """Get monitoring status for user"""
    user_id = current_user["user_id"]
    
    # Try to get from database
    if db.pool:
        row = await db.fetchone(
            "SELECT * FROM monitoring_sessions WHERE user_id = $1 AND is_active = true",
            user_id
        )
        if row:
            return MonitoringStatus(
                user_id=user_id,
                is_active=True,
                gifts_found=row['gifts_found'],
                last_check=row['started_at']
            )
    
    # Default response
    return MonitoringStatus(
        user_id=user_id,
        is_active=False,
        gifts_found=0,
        last_check=None
    )

@app.post("/api/v1/monitoring/start")
async def start_monitoring(
    request: StartMonitoringRequest,
    current_user: dict = Depends(verify_token)
):
    """Start monitoring for user"""
    user_id = current_user["user_id"]
    
    # Save to database if available
    if db.pool:
        await db.execute(
            """
            INSERT INTO monitoring_sessions (user_id, is_active) 
            VALUES ($1, true)
            ON CONFLICT (user_id) WHERE is_active = true
            DO UPDATE SET started_at = CURRENT_TIMESTAMP
            """,
            user_id
        )
    
    # TODO: Start actual monitoring process
    logger.info(f"Started monitoring for user {user_id}")
    
    return {
        "status": "started",
        "user_id": user_id,
        "target_games": request.target_games,
        "interval": request.interval
    }

@app.post("/api/v1/monitoring/stop")
async def stop_monitoring(current_user: dict = Depends(verify_token)):
    """Stop monitoring for user"""
    user_id = current_user["user_id"]
    
    # Update database if available
    if db.pool:
        await db.execute(
            """
            UPDATE monitoring_sessions 
            SET is_active = false, ended_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND is_active = true
            """,
            user_id
        )
    
    # TODO: Stop actual monitoring process
    logger.info(f"Stopped monitoring for user {user_id}")
    
    return {"status": "stopped", "user_id": user_id}

@app.get("/api/v1/user/settings", response_model=UserSettings)
async def get_user_settings(current_user: dict = Depends(verify_token)):
    """Get user settings"""
    user_id = current_user["user_id"]
    
    # Try to get from database
    if db.pool:
        row = await db.fetchone(
            "SELECT * FROM user_settings WHERE user_id = $1",
            user_id
        )
        if row:
            return UserSettings(
                notifications_enabled=row['notifications_enabled'],
                monitor_interval=row['monitor_interval'],
                target_games=row['target_games'] or []
            )
    
    # Default settings
    return UserSettings(
        notifications_enabled=True,
        monitor_interval=300,
        target_games=["Hamster Kombat", "Major", "Tomarket"]
    )

@app.put("/api/v1/user/settings")
async def update_user_settings(
    settings: UserSettings,
    current_user: dict = Depends(verify_token)
):
    """Update user settings"""
    user_id = current_user["user_id"]
    
    # Save to database if available
    if db.pool:
        await db.execute(
            """
            INSERT INTO user_settings (user_id, notifications_enabled, monitor_interval, target_games)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                notifications_enabled = $2,
                monitor_interval = $3,
                target_games = $4,
                updated_at = CURRENT_TIMESTAMP
            """,
            user_id,
            settings.notifications_enabled,
            settings.monitor_interval,
            settings.target_games
        )
    
    return {"status": "updated", "settings": settings}

@app.post("/api/v1/test/notification")
async def test_notification(current_user: dict = Depends(verify_token)):
    """Send test notification"""
    user_id = current_user["user_id"]
    
    success = await push_service.send_notification(
        user_id,
        "Test Notification",
        "This is a test notification from Telegram Gift Monitor"
    )
    
    return {
        "status": "sent" if success else "failed",
        "user_id": user_id
    }

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Main entry point
if __name__ == "__main__":
    try:
        logger.info("Starting Telegram Gift Monitor API...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        import sys
        sys.exit(1)