"""Send a real test broadcast through Telegram."""

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Bot

from database.connection import Database
from admin.services.broadcast_service import BroadcastService
from config.settings import Settings

load_dotenv()
settings = Settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_test_broadcast():
    """Send a real test broadcast."""

    print("\n" + "=" * 60)
    print("SENDING REAL TEST BROADCAST")
    print("=" * 60)

    # Get bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("\n❌ TELEGRAM_BOT_TOKEN not found in .env")
        return

    # Initialize bot
    bot = Bot(token=bot_token)

    try:
        bot_info = await bot.get_me()
        print(f"\n✅ Connected to bot: @{bot_info.username}")
    except Exception as e:
        print(f"\n❌ Failed to connect: {e}")
        return

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()
    print("✅ Database initialized")

    # Create service
    service = BroadcastService(db, bot)

    # Get user count
    user_count = await service.count_target_users("all")
    print(f"\n📊 Users in database: {user_count}")

    if user_count == 0:
        print("\n⚠️  No users found!")
        print("   Please register at least one user first:")
        print("   1. Start your bot: python run.py")
        print("   2. Send /start to your bot in Telegram")
        print("   3. Complete registration")
        print("   4. Run this test again")
        await db.close()
        return

    # Test message
    test_message = """🧪 *Broadcast System Test*

This is a real test message from the enhanced admin broadcast system.

✅ *Features tested:*
• Markdown formatting
• Real-time sending
• Progress tracking
• Error handling

If you're seeing this, everything is working perfectly!

🎉 *The broadcast system is production-ready!*"""

    print("\n" + "=" * 60)
    print("MESSAGE PREVIEW")
    print("=" * 60)
    print(test_message)
    print("=" * 60)
    print(f"\n🎯 Will send to: {user_count} user(s)")
    print("⚠️  This will send a REAL Telegram message!\n")

    # Progress tracking
    async def show_progress(sent, failed, total):
        percentage = ((sent + failed) / total * 100) if total > 0 else 0
        bar_length = 20
        filled = int(((sent + failed) / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r📤 {bar} {percentage:.0f}% | ✅ {sent} | ❌ {failed} | 📊 {total}", end="", flush=True)

    # Send broadcast
    print("📤 Sending broadcast...\n")

    try:
        result = await service.broadcast_message(
            message=test_message,
            filter_type="all",
            progress_callback=show_progress,
        )

        print("\n\n" + "=" * 60)
        print("✅ BROADCAST COMPLETED")
        print("=" * 60)
        print(f"\n📊 Results:")
        print(f"   Total users: {result['total']}")
        print(f"   ✅ Successfully sent: {result['sent']}")
        print(f"   ❌ Failed: {result['failed']}")

        if result['total'] > 0:
            success_rate = (result['sent'] / result['total']) * 100
            print(f"   📈 Success rate: {success_rate:.1f}%")

        if result['failed'] > 0:
            print(f"\n⚠️  Failed sends:")
            for failed_user in result['failed_users']:
                print(f"   User {failed_user['user_id']}: {failed_user['error']}")

        if result['sent'] > 0:
            print("\n✅ SUCCESS! Check your Telegram to see the message!")
            print("   The broadcast system is working perfectly! 🎉")
        else:
            print("\n⚠️  No messages were sent. Check errors above.")

    except Exception as e:
        print(f"\n\n❌ Broadcast failed: {e}")
        logger.exception("Broadcast error")

    finally:
        await db.close()
        print("\n✅ Database connection closed")


if __name__ == "__main__":
    print("\n🚀 Starting real broadcast test...")
    print("⏳ Press Ctrl+C to cancel at any time\n")

    try:
        asyncio.run(send_test_broadcast())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        logger.exception("Test error")
