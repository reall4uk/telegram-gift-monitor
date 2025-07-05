from fastapi import APIRouter

router = APIRouter()

@router.get("/api/config")
async def get_config():
    """Отдать конфигурацию приложения"""
    config = {
        "monitoring_channels": [
            "@News_Collections",
            "@gifts_detector",
            "@GiftsTracker",
            "@new_gifts_alert_news"
        ],
        "required_channel": "@analizatorNFT",
        "api_url": "http://your-server.com:8000",
        "min_update_interval": 30,
        "features": {
            "background_monitoring": True,
            "sound_notifications": True
        }
    }
    
    # Добавляем подпись для проверки
    import hashlib
    import json
    config_string = json.dumps(config, sort_keys=True)
    signature = hashlib.sha256(config_string.encode()).hexdigest()
    config["signature"] = signature
    
    return config