#!/usr/bin/env python3
"""
Monitor specific channels and groups for gift notifications
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

load_dotenv()

# Каналы и группы для мониторинга
MONITOR_CHATS = [
    "@gift_newstg",          # Gift News🎁 - канал
    "@News_Collections",     # News_Collections - группа
    "@TestGroupNewsNFT",     # TestGroupNewsNFT - группа
    "@ton_vseznayka",       # TON Всезнайка - канал
    "@analizatorNFT",       # A.NFT - канал
    "@tonnel_en",           # Tonnel Network - канал
    "@official_mrkt",       # MRKT - канал
    "-1002086760056",       # LEAN HUSTLE CRYPTO - канал по ID
    "-1002043309840",       # @collectibles - канал по ID
]

# Ключевые слова для поиска подарков
GIFT_KEYWORDS = [
    "gift", "gifts", "подарок", "подарки",
    "new limited", "новый лимитированный",
    "редкий", "rare", "limited",
    "drop", "дроп", "airdrop",
    "🎁", "💎", "⭐", "stars",
    "price:", "цена:", "стоимость:",
    "available:", "доступно:", "осталось:",
    "collectible", "коллекционный",
    "nft", "токен"
]

# Статистика
stats = {
    "total_messages": 0,
    "gift_messages": 0,
    "channels": {}
}

def is_monitored_chat(chat_username: str, chat_id: int) -> bool:
    """Check if chat should be monitored"""
    # Check by username
    if chat_username and f"@{chat_username}" in MONITOR_CHATS:
        return True
    # Check by ID
    if str(chat_id) in MONITOR_CHATS:
        return True
    return False

def contains_gift_keywords(text: str) -> list:
    """Check if text contains gift keywords, return found keywords"""
    if not text:
        return []
    
    text_lower = text.lower()
    found_keywords = []
    
    for keyword in GIFT_KEYWORDS:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

async def main():
    app = Client(
        "gift_monitor",
        api_id=os.getenv('TELEGRAM_API_ID'),
        api_hash=os.getenv('TELEGRAM_API_HASH'),
        phone_number=os.getenv('TELEGRAM_PHONE')
    )
    
    @app.on_message(filters.chat(MONITOR_CHATS))
    async def handle_message(client: Client, message: Message):
        # Update statistics
        stats["total_messages"] += 1
        
        # Get chat info
        chat_name = message.chat.title or message.chat.first_name or "Unknown"
        chat_username = f"@{message.chat.username}" if message.chat.username else f"ID:{message.chat.id}"
        
        # Update channel stats
        if chat_username not in stats["channels"]:
            stats["channels"][chat_username] = {"total": 0, "gifts": 0}
        stats["channels"][chat_username]["total"] += 1
        
        # Get message text
        text = message.text or message.caption or ""
        
        # Check for gift keywords
        found_keywords = contains_gift_keywords(text)
        
        # Print message info
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] 📨 Message #{stats['total_messages']}")
        print(f"📍 From: {chat_name} ({chat_username})")
        
        if found_keywords:
            stats["gift_messages"] += 1
            stats["channels"][chat_username]["gifts"] += 1
            
            print(f"🎁 ⚡ GIFT DETECTED! ⚡")
            print(f"🔑 Keywords found: {', '.join(found_keywords)}")
            print(f"📝 Text: {text[:200]}...")
            
            if message.chat.username:
                print(f"🔗 Link: https://t.me/{message.chat.username}/{message.id}")
            
            # Here you would send push notification in the full system
            print(f"📱 [Would send push notification]")
        else:
            print(f"📝 Regular message (first 100 chars): {text[:100]}...")
        
        # Show statistics
        print(f"📊 Stats: Total: {stats['total_messages']} | Gifts: {stats['gift_messages']}")
    
    async with app:
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        print(f"\n🔍 Monitoring {len(MONITOR_CHATS)} chats for gifts:")
        
        # Show monitored chats
        for chat in MONITOR_CHATS:
            try:
                chat_obj = await app.get_chat(chat)
                print(f"  ✅ {chat_obj.title} ({chat})")
            except:
                print(f"  ⚠️  {chat} (not accessible)")
        
        print(f"\n🎯 Looking for keywords: {', '.join(GIFT_KEYWORDS[:10])}...")
        print("\nPress Ctrl+C to stop\n")
        print("="*60)
        
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n📊 Final Statistics:")
        print(f"Total messages scanned: {stats['total_messages']}")
        print(f"Gift messages found: {stats['gift_messages']}")
        print(f"\nBy channel:")
        for channel, data in stats["channels"].items():
            print(f"  {channel}: {data['gifts']}/{data['total']} gifts")
        print("\n✅ Monitoring stopped!")