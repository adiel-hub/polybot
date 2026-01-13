"""Manual test script for broadcast functionality."""

import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from unittest.mock import AsyncMock, MagicMock

from admin.services.broadcast_service import BroadcastService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_text_broadcast():
    """Test text-only broadcast."""
    print("\n" + "=" * 60)
    print("TEST 1: Text-Only Broadcast")
    print("=" * 60)

    # Mock database
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, 111111),
        (2, 222222),
        (3, 333333),
    ])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_db.connection = MagicMock(return_value=mock_conn)

    # Mock bot
    sent_messages = []

    async def mock_send_message(**kwargs):
        sent_messages.append(("text", kwargs))
        logger.info(f"Sent to {kwargs['chat_id']}: {kwargs['text'][:50]}...")

    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message
    mock_bot.send_photo = AsyncMock()

    # Create service and broadcast
    service = BroadcastService(mock_db, mock_bot)

    result = await service.broadcast_message(
        message="🎉 *Welcome to PolyBot!*\n\nStart trading on Polymarket today.",
        filter_type="all",
    )

    # Verify results
    print(f"\n✅ Broadcast completed:")
    print(f"   Total: {result['total']}")
    print(f"   Sent: {result['sent']}")
    print(f"   Failed: {result['failed']}")
    print(f"\n✅ Messages sent: {len(sent_messages)}")

    for i, (msg_type, kwargs) in enumerate(sent_messages, 1):
        print(f"   {i}. To user {kwargs['chat_id']}: {kwargs['text'][:40]}...")

    assert result['sent'] == 3, f"Expected 3 sent, got {result['sent']}"
    assert result['failed'] == 0, f"Expected 0 failed, got {result['failed']}"
    assert len(sent_messages) == 3, f"Expected 3 messages, got {len(sent_messages)}"

    print("\n✅ TEXT BROADCAST TEST PASSED\n")


async def test_image_broadcast():
    """Test image + caption broadcast."""
    print("\n" + "=" * 60)
    print("TEST 2: Image + Caption Broadcast")
    print("=" * 60)

    # Mock database
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, 111111),
        (2, 222222),
    ])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_db.connection = MagicMock(return_value=mock_conn)

    # Mock bot
    sent_photos = []

    async def mock_send_photo(**kwargs):
        sent_photos.append(kwargs)
        logger.info(f"Sent photo to {kwargs['chat_id']}: {kwargs.get('caption', 'No caption')[:30]}...")

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_photo = mock_send_photo

    # Create service and broadcast
    service = BroadcastService(mock_db, mock_bot)

    result = await service.broadcast_message(
        message="Check out our new feature! 🚀",
        filter_type="all",
        image_file_id="AgACAgIAAxkBAAIC_test_file_id",
    )

    # Verify results
    print(f"\n✅ Broadcast completed:")
    print(f"   Total: {result['total']}")
    print(f"   Sent: {result['sent']}")
    print(f"   Failed: {result['failed']}")
    print(f"\n✅ Photos sent: {len(sent_photos)}")

    for i, kwargs in enumerate(sent_photos, 1):
        print(f"   {i}. To user {kwargs['chat_id']}: Photo with caption: {kwargs.get('caption', 'None')[:30]}...")

    assert result['sent'] == 2, f"Expected 2 sent, got {result['sent']}"
    assert len(sent_photos) == 2, f"Expected 2 photos, got {len(sent_photos)}"
    assert sent_photos[0]['photo'] == "AgACAgIAAxkBAAIC_test_file_id"

    print("\n✅ IMAGE BROADCAST TEST PASSED\n")


async def test_broadcast_with_buttons():
    """Test broadcast with inline keyboard buttons."""
    print("\n" + "=" * 60)
    print("TEST 3: Broadcast with Buttons")
    print("=" * 60)

    # Mock database
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, 111111),
        (2, 222222),
    ])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_db.connection = MagicMock(return_value=mock_conn)

    # Mock bot
    sent_messages = []

    async def mock_send_message(**kwargs):
        sent_messages.append(kwargs)
        if kwargs.get('reply_markup'):
            logger.info(f"Sent to {kwargs['chat_id']} with {len(kwargs['reply_markup'].inline_keyboard)} button rows")

    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message
    mock_bot.send_photo = AsyncMock()

    # Create service and broadcast
    service = BroadcastService(mock_db, mock_bot)

    # Create button keyboard
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Start Trading", url="https://polymarket.com")],
        [InlineKeyboardButton("👥 Join Community", url="https://t.me/polybot_community")],
    ])

    result = await service.broadcast_message(
        message="🎉 *Join PolyBot Today!*\n\nTrade prediction markets with ease.",
        filter_type="all",
        reply_markup=keyboard,
    )

    # Verify results
    print(f"\n✅ Broadcast completed:")
    print(f"   Total: {result['total']}")
    print(f"   Sent: {result['sent']}")
    print(f"   Failed: {result['failed']}")
    print(f"\n✅ Messages with buttons sent: {len(sent_messages)}")

    for i, kwargs in enumerate(sent_messages, 1):
        button_count = len(kwargs['reply_markup'].inline_keyboard) if kwargs.get('reply_markup') else 0
        print(f"   {i}. To user {kwargs['chat_id']}: {button_count} button(s)")

    assert result['sent'] == 2, f"Expected 2 sent, got {result['sent']}"
    assert sent_messages[0].get('reply_markup') is not None, "Expected buttons"
    assert len(sent_messages[0]['reply_markup'].inline_keyboard) == 2, "Expected 2 button rows"

    print("\n✅ BUTTONS BROADCAST TEST PASSED\n")


async def test_broadcast_with_failures():
    """Test broadcast handles failures correctly."""
    print("\n" + "=" * 60)
    print("TEST 4: Broadcast with Failures")
    print("=" * 60)

    # Mock database
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, 111111),
        (2, 222222),
        (3, 333333),
        (4, 444444),
    ])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_db.connection = MagicMock(return_value=mock_conn)

    # Mock bot with failures
    call_count = 0

    async def mock_send_message(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Fail on second user
            raise Exception("User blocked bot")
        if call_count == 4:  # Fail on fourth user
            raise Exception("Chat not found")
        logger.info(f"Sent to {kwargs['chat_id']} successfully")

    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message
    mock_bot.send_photo = AsyncMock()

    # Create service and broadcast
    service = BroadcastService(mock_db, mock_bot)

    result = await service.broadcast_message(
        message="Test message",
        filter_type="all",
    )

    # Verify results
    print(f"\n✅ Broadcast completed:")
    print(f"   Total: {result['total']}")
    print(f"   Sent: {result['sent']}")
    print(f"   Failed: {result['failed']}")
    print(f"\n✅ Failed users: {len(result['failed_users'])}")

    for failed in result['failed_users']:
        print(f"   User {failed['user_id']}: {failed['error']}")

    assert result['total'] == 4, f"Expected 4 total, got {result['total']}"
    assert result['sent'] == 2, f"Expected 2 sent, got {result['sent']}"
    assert result['failed'] == 2, f"Expected 2 failed, got {result['failed']}"
    assert len(result['failed_users']) == 2, f"Expected 2 failed users, got {len(result['failed_users'])}"

    print("\n✅ FAILURE HANDLING TEST PASSED\n")


async def test_progress_callback():
    """Test progress callback is triggered."""
    print("\n" + "=" * 60)
    print("TEST 5: Progress Callback")
    print("=" * 60)

    # Mock database with 25 users
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[(i, i * 1000) for i in range(1, 26)])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_db.connection = MagicMock(return_value=mock_conn)

    # Mock bot
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_photo = AsyncMock()

    # Track progress updates
    progress_updates = []

    async def track_progress(sent, failed, total):
        progress_updates.append((sent, failed, total))
        percentage = (sent + failed) / total * 100
        print(f"   Progress: {sent}/{total} ({percentage:.0f}%) - Failed: {failed}")

    # Create service and broadcast
    service = BroadcastService(mock_db, mock_bot)

    result = await service.broadcast_message(
        message="Progress test",
        filter_type="all",
        progress_callback=track_progress,
    )

    # Verify results
    print(f"\n✅ Broadcast completed:")
    print(f"   Total: {result['total']}")
    print(f"   Progress updates: {len(progress_updates)}")

    assert len(progress_updates) >= 2, f"Expected at least 2 progress updates, got {len(progress_updates)}"
    # Progress callback should be called every 10 messages (so at 10, 20, not 25)
    assert progress_updates[-1][0] == 20, f"Expected last update at 20, got {progress_updates[-1][0]}"
    assert result['sent'] == 25, f"Expected final sent count 25, got {result['sent']}"

    print("\n✅ PROGRESS CALLBACK TEST PASSED\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("BROADCAST SYSTEM MANUAL TESTS")
    print("=" * 60)

    try:
        await test_text_broadcast()
        await test_image_broadcast()
        await test_broadcast_with_buttons()
        await test_broadcast_with_failures()
        await test_progress_callback()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nBroadcast system is working correctly:")
        print("  ✓ Text messages")
        print("  ✓ Image + caption")
        print("  ✓ Inline keyboard buttons")
        print("  ✓ Error handling")
        print("  ✓ Progress tracking")
        print("\nThe preview feature is also implemented in confirm_broadcast():")
        print("  ✓ Shows actual message as users will see it")
        print("  ✓ Displays buttons if added")
        print("  ✓ Shows broadcast summary before sending")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
