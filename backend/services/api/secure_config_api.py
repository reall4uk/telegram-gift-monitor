from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import hashlib
import json
import os
from datetime import datetime, timedelta
import jwt

router = APIRouter()

# Секретный ключ для JWT (храните в переменных окружения!)
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-this')
JWT_ALGORITHM = "HS256"

# Конфигурация приложения (в production храните в БД)
APP_CONFIG = {
    "monitoring_channels": [
        "@News_Collections",
        "@gifts_detector",
        "@GiftsTracker",
        "@new_gifts_alert_news"
    ],
    "required_channel": "@analizatorNFT",
    "api_url": "https://your-domain.com/api",
    "min_update_interval": 30,
    "features": {
        "background_monitoring": True,
        "sound_notifications": True,
        "max_price_filter": 100000
    },
    "security": {
        "min_app_version": "1.0.0",
        "force_update": False,
        "blocked_regions": []
    }
}

# Токен бота (НИКОГДА не храните в коде!)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

@router.post("/api/auth/app")
async def authenticate_app(
    app_version: str = Header(...),
    app_signature: str = Header(...),
    device_id: Optional[str] = Header(None)
):
    """Аутентификация приложения и выдача токена"""
    
    # Проверяем подпись приложения
    expected_signature = hashlib.sha256(
        f"{app_version}:{JWT_SECRET}".encode()
    ).hexdigest()
    
    if app_signature != expected_signature:
        raise HTTPException(status_code=403, detail="Invalid app signature")
    
    # Создаем JWT токен для приложения
    payload = {
        "app_version": app_version,
        "device_id": device_id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {
        "token": token,
        "expires_in": 604800  # 7 дней в секундах
    }

@router.get("/api/config")
async def get_config(
    authorization: str = Header(...),
    x_app_version: str = Header(...)
):
    """Получить конфигурацию приложения"""
    
    # Проверяем JWT токен
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Проверяем версию приложения
    app_version = payload.get("app_version", "0.0.0")
    min_version = APP_CONFIG["security"]["min_app_version"]
    
    if _compare_versions(app_version, min_version) < 0:
        APP_CONFIG["security"]["force_update"] = True
    
    # Создаем копию конфигурации
    config = APP_CONFIG.copy()
    
    # Добавляем подпись для проверки целостности
    config_string = json.dumps(config, sort_keys=True)
    signature = hashlib.sha256(
        f"{config_string}:{JWT_SECRET}".encode()
    ).hexdigest()
    
    config["signature"] = signature
    config["timestamp"] = datetime.utcnow().isoformat()
    
    return config

@router.get("/api/bot-token")
async def get_bot_token(
    authorization: str = Header(...),
    user_id: str = Header(...)
):
    """Получить токен бота (только для авторизованных приложений)"""
    
    # Проверяем JWT токен
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Логируем запрос (для безопасности)
    print(f"[Security] Bot token requested by user {user_id} from device {payload.get('device_id')}")
    
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    
    # Шифруем токен для дополнительной защиты
    encrypted_token = _simple_encrypt(BOT_TOKEN, user_id)
    
    return {
        "token": encrypted_token,
        "expires_in": 3600  # 1 час
    }

def _compare_versions(v1: str, v2: str) -> int:
    """Сравнить версии (1 если v1 > v2, -1 если v1 < v2, 0 если равны)"""
    v1_parts = [int(x) for x in v1.split('.')]
    v2_parts = [int(x) for x in v2.split('.')]
    
    for i in range(max(len(v1_parts), len(v2_parts))):
        v1_part = v1_parts[i] if i < len(v1_parts) else 0
        v2_part = v2_parts[i] if i < len(v2_parts) else 0
        
        if v1_part > v2_part:
            return 1
        elif v1_part < v2_part:
            return -1
    
    return 0

def _simple_encrypt(text: str, key: str) -> str:
    """Простое шифрование XOR (для production используйте AES)"""
    key_hash = hashlib.sha256(key.encode()).digest()
    encrypted = []
    
    for i, char in enumerate(text):
        encrypted.append(chr(ord(char) ^ key_hash[i % len(key_hash)]))
    
    import base64
    return base64.b64encode(''.join(encrypted).encode()).decode()

# Добавьте в main.py:
# from secure_config import router as secure_config_router
# app.include_router(secure_config_router)