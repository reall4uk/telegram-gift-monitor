#!/usr/bin/env python3
"""
Quick test script to verify Telegram monitoring works
Run this before starting the full system
"""

import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

# Load environment variables
load_dotenv()

# Test configuration
TEST_CHANNEL = "@News_Collections"  # Replace with your test channel
GIFT_KEYWORDS = ["gift", "подарок", "new", "limited", "редкий"]

async def main():
    """Test Telegram connection and monitoring"""
    
    print("🚀 Starting Telegram Monitor Test...")
    print("-" * 50)
    
    # Check environment variables
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    
    if not all([api_id, api_hash, phone]):
        print("❌ Error: Missing Telegram credentials in .env file")
        print("Please set: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE")
        return
    
    print("✅ Credentials loaded")
    print(f"📱 Phone: {phone}")
    
    # Create client
    app = Client(
        "test_session",
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone
    )
    
    message_count = 0
    gift_count = 0
    
    @app.on_message(filters.channel)
    async def handle_message(client: Client, message: Message):
        nonlocal message_count, gift_count
        message_count += 1
        
        # Get channel info
        channel = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
        
        # Get message text
        text = message.text or message.caption or ""
        
        # Check for gift keywords
        text_lower = text.lower()
        is_gift = any(keyword in text_lower for keyword in GIFT_KEYWORDS)
        
        if is_gift:
            gift_count += 1
            print(f"\n🎁 GIFT DETECTED in {channel}!")
            print(f"📝 Preview: {text[:100]}...")
            print(f"🔗 Link: https://t.me/{message.chat.username}/{message.id}")
        else:
            print(f"📨 Message {message_count} from {channel} (not a gift)")
    
    try:
        async with app:
            print("\n✅ Connected to Telegram!")
            
            # Get current user info
            me = await app.get_me()
            print(f"👤 Logged in as: {me.first_name} (@{me.username})")
            
            # Try to join test channel
            try:
                await app.join_chat(TEST_CHANNEL)
                print(f"✅ Joined {TEST_CHANNEL}")
            except Exception as e:
                print(f"ℹ️ Could not join {TEST_CHANNEL}: {e}")
            
            # List current chats
            print("\n📋 Your channels:")
            count = 0
            async for dialog in app.get_dialogs():
                if dialog.chat.type in ["channel", "supergroup"]:
                    print(f"  - {dialog.chat.title} (@{dialog.chat.username})")
                    count += 1
                    if count >= 10:  # Limit output
                        break
            
            print(f"\n🔍 Monitoring for gift messages...")
            print("Press Ctrl+C to stop\n")
            
            # Keep running
            await asyncio.Event().wait()
            
    except KeyboardInterrupt:
        print(f"\n\n📊 Test Results:")
        print(f"  - Messages seen: {message_count}")
        print(f"  - Gifts detected: {gift_count}")
        print("\n✅ Test completed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Check your internet connection")
        print("2. Verify Telegram credentials are correct")
        print("3. Make sure you can login to Telegram with this phone number")
        print("4. Delete 'test_session.session' file if it exists and try again")

if __name__ == "__main__":
    asyncio.run(main())