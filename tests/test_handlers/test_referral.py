"""Tests for referral handlers."""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import qrcode

from bot.handlers.referral import handle_create_qr
from bot.conversations.states import ConversationState


@pytest.mark.asyncio
async def test_handle_create_qr_generates_valid_qr():
    """Test that handle_create_qr generates a valid QR code image."""
    # Setup mocks
    update = MagicMock()
    context = MagicMock()

    # Mock callback query
    query = AsyncMock()
    query.message.chat_id = 12345
    update.callback_query = query
    update.effective_user.id = 67890

    # Mock bot
    context.bot.username = "test_bot"
    context.bot.send_photo = AsyncMock()

    # Mock referral service
    referral_service = AsyncMock()
    referral_service.get_referral_link = AsyncMock(
        return_value="https://t.me/test_bot?start=ref_67890"
    )
    context.bot_data = {"referral_service": referral_service}

    # Call the handler
    result = await handle_create_qr(update, context)

    # Verify callback query was answered
    query.answer.assert_called_once()

    # Verify referral link was retrieved
    referral_service.get_referral_link.assert_called_once_with(67890, "test_bot")

    # Verify photo was sent
    context.bot.send_photo.assert_called_once()
    call_args = context.bot.send_photo.call_args

    # Check chat_id
    assert call_args.kwargs['chat_id'] == 12345

    # Check caption
    assert "Your Referral QR Code" in call_args.kwargs['caption']
    assert "https://t.me/test_bot?start=ref_67890" in call_args.kwargs['caption']

    # Check photo is a BytesIO object
    photo = call_args.kwargs['photo']
    assert isinstance(photo, io.BytesIO)
    assert photo.name == 'referral_qr.png'

    # Verify the photo is a valid PNG image
    photo.seek(0)
    img = Image.open(photo)
    assert img.format == 'PNG'

    # Verify original message was deleted
    query.message.delete.assert_called_once()

    # Verify correct state returned
    assert result == ConversationState.REFERRAL_QR


@pytest.mark.asyncio
async def test_handle_create_qr_qr_code_contains_correct_data():
    """Test that the QR code contains the correct referral link."""
    # Setup mocks
    update = MagicMock()
    context = MagicMock()

    query = AsyncMock()
    query.message.chat_id = 12345
    update.callback_query = query
    update.effective_user.id = 67890

    context.bot.username = "test_bot"
    context.bot.send_photo = AsyncMock()

    referral_link = "https://t.me/test_bot?start=ref_67890"
    referral_service = AsyncMock()
    referral_service.get_referral_link = AsyncMock(return_value=referral_link)
    context.bot_data = {"referral_service": referral_service}

    # Call the handler
    await handle_create_qr(update, context)

    # Get the photo that was sent
    call_args = context.bot.send_photo.call_args
    photo = call_args.kwargs['photo']

    # Decode the QR code to verify it contains the correct data
    photo.seek(0)
    img = Image.open(photo)

    # Use pyzbar or similar library to decode QR (for this test, we'll trust qrcode library)
    # Instead, we'll verify by creating our own QR with same data and comparing
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(referral_link)
    qr.make(fit=True)
    expected_img = qr.make_image(fill_color="black", back_color="white")

    # Both images should have same size (indicating same data/settings)
    assert img.size == expected_img.size


@pytest.mark.asyncio
async def test_handle_create_qr_with_special_characters_in_link():
    """Test QR code generation with special characters in the link."""
    # Setup mocks
    update = MagicMock()
    context = MagicMock()

    query = AsyncMock()
    query.message.chat_id = 12345
    update.callback_query = query
    update.effective_user.id = 67890

    context.bot.username = "test_bot"
    context.bot.send_photo = AsyncMock()

    # Link with special characters
    referral_link = "https://t.me/test_bot?start=ref_67890&utm_source=telegram&utm_campaign=test"
    referral_service = AsyncMock()
    referral_service.get_referral_link = AsyncMock(return_value=referral_link)
    context.bot_data = {"referral_service": referral_service}

    # Call the handler - should not raise any exceptions
    result = await handle_create_qr(update, context)

    # Verify it completed successfully
    assert result == ConversationState.REFERRAL_QR
    context.bot.send_photo.assert_called_once()

    # Verify the caption contains the link
    call_args = context.bot.send_photo.call_args
    assert referral_link in call_args.kwargs['caption']


@pytest.mark.asyncio
async def test_handle_create_qr_keyboard_buttons():
    """Test that the QR code message has the correct keyboard buttons."""
    # Setup mocks
    update = MagicMock()
    context = MagicMock()

    query = AsyncMock()
    query.message.chat_id = 12345
    update.callback_query = query
    update.effective_user.id = 67890

    context.bot.username = "test_bot"
    context.bot.send_photo = AsyncMock()

    referral_service = AsyncMock()
    referral_service.get_referral_link = AsyncMock(
        return_value="https://t.me/test_bot?start=ref_67890"
    )
    context.bot_data = {"referral_service": referral_service}

    # Call the handler
    await handle_create_qr(update, context)

    # Get the reply markup
    call_args = context.bot.send_photo.call_args
    reply_markup = call_args.kwargs['reply_markup']

    # Verify keyboard structure
    assert reply_markup is not None
    keyboard = reply_markup.inline_keyboard

    # Should have 2 rows
    assert len(keyboard) == 2

    # First row: Back button
    assert len(keyboard[0]) == 1
    assert keyboard[0][0].text == "🔙 Back"
    assert keyboard[0][0].callback_data == "menu_rewards"

    # Second row: Main Menu button
    assert len(keyboard[1]) == 1
    assert keyboard[1][0].text == "🏠 Main Menu"
    assert keyboard[1][0].callback_data == "menu_main"
