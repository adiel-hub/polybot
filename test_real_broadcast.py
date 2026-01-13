"""Real broadcast test with actual Telegram bot.

This script tests the broadcast functionality with a real bot and database.
It will send a test broadcast to verify everything works.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from database.connection import Database
from admin.services.broadcast_service import BroadcastService
from config.settings import Settings

# Load environment variables
load_dotenv()
settings = Settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_real_broadcast():
    """Test broadcast with real bot and database."""

    # Get bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env file")
        return

    print("\n" + "=" * 60)
    print("REAL BROADCAST TEST")
    print("=" * 60)

    # Initialize bot
    bot = Bot(token=bot_token)

    # Test bot connection
    try:
        bot_info = await bot.get_me()
        print(f"\n✅ Bot connected: @{bot_info.username}")
    except Exception as e:
        print(f"\n❌ Failed to connect to bot: {e}")
        return

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()
    print("✅ Database connected")

    # Create broadcast service
    service = BroadcastService(db, bot)

    # Get user counts
    all_count = await service.count_target_users("all")
    active_count = await service.count_target_users("active")
    balance_count = await service.count_target_users("with_balance")

    print(f"\n📊 User Statistics:")
    print(f"   All users: {all_count}")
    print(f"   Active users: {active_count}")
    print(f"   With balance: {balance_count}")

    if all_count == 0:
        print("\n⚠️  No users in database - cannot test broadcast")
        print("   Register at least one user first by starting the bot with /start")
        return

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("⚠️  WARNING: This will send a REAL test broadcast!")
    print("=" * 60)
    print(f"\nTest broadcast will be sent to: {all_count} user(s)")
    print("\nMessage preview:")
    print("-" * 60)
    print("🧪 *Test Broadcast*")
    print("")
    print("This is a test message from the admin broadcast system.")
    print("")
    print("✅ If you see this, the broadcast feature is working!")
    print("-" * 60)

    response = input("\n👉 Send test broadcast? (yes/no): ").lower().strip()

    if response != "yes":
        print("\n❌ Test cancelled")
        return

    # Progress tracking
    progress_updates = []

    async def track_progress(sent, failed, total):
        percentage = (sent + failed) / total * 100 if total > 0 else 0
        bar_length = 20
        filled = int((sent + failed) / total * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        print(f"\r📤 {bar} {percentage:.0f}% | Sent: {sent} | Failed: {failed} | Total: {total}", end="", flush=True)
        progress_updates.append((sent, failed, total))

    # Send test broadcast
    print("\n\n📤 Sending test broadcast...\n")

    try:
        result = await service.broadcast_message(
            message="🧪 *Test Broadcast*\n\nThis is a test message from the admin broadcast system.\n\n✅ If you see this, the broadcast feature is working!",
            filter_type="all",
            progress_callback=track_progress,
        )

        print("\n\n" + "=" * 60)
        print("✅ BROADCAST COMPLETED")
        print("=" * 60)
        print(f"\n📊 Results:")
        print(f"   Total users: {result['total']}")
        print(f"   Successfully sent: {result['sent']}")
        print(f"   Failed: {result['failed']}")
        print(f"   Success rate: {result['sent']/result['total']*100:.1f}%")

        if result['failed'] > 0:
            print(f"\n⚠️  Failed sends ({result['failed']}):")
            for failed_user in result['failed_users'][:5]:  # Show first 5
                print(f"   User {failed_user['user_id']}: {failed_user['error']}")
            if len(result['failed_users']) > 5:
                print(f"   ... and {len(result['failed_users']) - 5} more")

        if result['sent'] > 0:
            print(f"\n✅ Broadcast feature is working correctly!")
        else:
            print(f"\n❌ No messages were sent - check errors above")

    except Exception as e:
        print(f"\n\n❌ Broadcast failed: {e}")
        logger.exception("Broadcast error")
        return

    # Close database
    await db.close()
    print("\n✅ Database closed")


async def test_broadcast_with_buttons():
    """Test broadcast with inline keyboard buttons."""

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not found")
        return

    print("\n\n" + "=" * 60)
    print("BROADCAST WITH BUTTONS TEST")
    print("=" * 60)

    bot = Bot(token=bot_token)
    db = Database(settings.database_path)
    await db.initialize()

    service = BroadcastService(db, bot)
    user_count = await service.count_target_users("all")

    if user_count == 0:
        print("\n⚠️  No users in database")
        await db.close()
        return

    # Create test buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Documentation", url="https://github.com/adiel-hub/polybot")],
        [InlineKeyboardButton("💬 Support", url="https://t.me/polybot_support")],
    ])

    print(f"\nTest will send to {user_count} user(s)")
    print("\nMessage preview:")
    print("-" * 60)
    print("🔘 *Button Test*")
    print("")
    print("Testing inline keyboard buttons.")
    print("")
    print("[📖 Documentation] [💬 Support]")
    print("-" * 60)

    response = input("\n👉 Send test with buttons? (yes/no): ").lower().strip()

    if response != "yes":
        print("\n❌ Test cancelled")
        await db.close()
        return

    print("\n📤 Sending...\n")

    try:
        result = await service.broadcast_message(
            message="🔘 *Button Test*\n\nTesting inline keyboard buttons.",
            filter_type="all",
            reply_markup=keyboard,
        )

        print(f"\n✅ Sent: {result['sent']}/{result['total']}")
        if result['sent'] > 0:
            print("✅ Buttons broadcast working!")

    except Exception as e:
        print(f"\n❌ Failed: {e}")

    await db.close()


async def test_broadcast_with_image():
    """Test broadcast with image (requires image file_id)."""

    print("\n\n" + "=" * 60)
    print("IMAGE BROADCAST TEST")
    print("=" * 60)
    print("\n⚠️  To test image broadcasts, you need a Telegram file_id")
    print("   1. Send any photo to your bot")
    print("   2. Get the file_id from bot logs")
    print("   3. Run this test with that file_id")
    print("\n💡 Skipping image test for now - manual testing recommended")


async def main():
    """Run all real broadcast tests."""

    print("\n" + "=" * 60)
    print("POLYBOT BROADCAST SYSTEM - REAL TESTS")
    print("=" * 60)
    print("\nThis will test the broadcast system with your actual bot")
    print("and database. Make sure you have:")
    print("  1. TELEGRAM_BOT_TOKEN in .env")
    print("  2. At least one registered user")
    print("  3. Database initialized")

    try:
        # Test 1: Basic text broadcast
        await test_real_broadcast()

        # Test 2: Broadcast with buttons
        await test_broadcast_with_buttons()

        # Test 3: Image info
        await test_broadcast_with_image()

        print("\n" + "=" * 60)
        print("✅ REAL BROADCAST TESTS COMPLETE")
        print("=" * 60)
        print("\nCheck your Telegram to verify you received the test messages!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        logger.exception("Test error")


if __name__ == "__main__":
    asyncio.run(main())
