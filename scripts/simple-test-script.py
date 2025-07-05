#!/usr/bin/env python3
"""
Simplified test to monitor ALL messages from ALL channels
"""

import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.types import Message

# Load environment variables
load_dotenv()

async def main():
    app = Client(
        "simple_test",
        api_id=os.getenv('TELEGRAM_API_ID'),
        api_hash=os.getenv('TELEGRAM_API_HASH'),
        phone_number=os.getenv('TELEGRAM_PHONE')
    )
    
    @app.on_message()
    async def handle_all_messages(client: Client, message: Message):
        # Show info about EVERY message
        chat_type = message.chat.type
        chat_name = message.chat.title or message.chat.first_name or "Unknown"
        chat_username = f"@{message.chat.username}" if message.chat.username else f"ID:{message.chat.id}"
        text = (message.text or message.caption or "")[:100]
        
        print(f"\n{'='*50}")
        print(f"📨 New message")
        print(f"📍 From: {chat_name} ({chat_username})")
        print(f"📝 Type: {chat_type}")
        print(f"💬 Text: {text}...")
        
        # Check for gift keywords
        keywords = ["gift", "подарок", "new", "limited", "редкий", "🎁"]
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in keywords):
            print(f"🎁 ⚡ POSSIBLE GIFT DETECTED! ⚡")
        
        print(f"{'='*50}")
    
    async with app:
        me = await app.get_me()
        print(f"✅ Logged in as: {me.first_name} (@{me.username})")
        print("\n🔍 Monitoring ALL messages from ALL chats...")
        print("Press Ctrl+C to stop\n")
        
        # List all channels
        print("📋 Your channels and groups:")
        count = 0
        async for dialog in app.get_dialogs(limit=100):
            if dialog.chat.type in ["channel", "supergroup", "group"]:
                username = f"@{dialog.chat.username}" if dialog.chat.username else f"ID:{dialog.chat.id}"
                print(f"  - {dialog.chat.title} ({username})")
                count += 1
        
        print(f"\nTotal channels/groups: {count}")
        print("\n" + "="*50 + "\n")
        
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Test stopped!")