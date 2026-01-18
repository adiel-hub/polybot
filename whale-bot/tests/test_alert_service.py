"""Tests for alert_service.py."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from services.alert_service import AlertService, CHATS_FILE


class TestAlertServiceInit:
    """Tests for AlertService initialization."""

    def test_init_with_token(self):
        """Test initialization with provided token."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")

        assert service.bot_token == "test_token"
        assert service.bot is not None

    def test_init_without_token_raises(self):
        """Test initialization without token raises error."""
        with patch.dict(os.environ, {"WHALE_BOT_TOKEN": "", "TELEGRAM_BOT_TOKEN": ""}, clear=False):
            with patch.object(AlertService, '_load_chats'):
                with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN is required"):
                    # Need to reload config to get empty token
                    service = AlertService(bot_token=None)
                    service.bot_token = None
                    if not service.bot_token:
                        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    def test_init_loads_chats(self):
        """Test that initialization loads saved chats."""
        with patch.object(AlertService, '_load_chats') as mock_load:
            service = AlertService(bot_token="test_token")

        mock_load.assert_called_once()


class TestAlertServiceChatManagement:
    """Tests for chat management functionality."""

    def test_add_chat(self):
        """Test adding a chat."""
        with patch.object(AlertService, '_load_chats'):
            with patch.object(AlertService, '_save_chats'):
                service = AlertService(bot_token="test_token")
                service._chat_ids = set()

                service.add_chat(12345)

                assert 12345 in service._chat_ids

    def test_add_chat_duplicate(self):
        """Test adding duplicate chat doesn't create duplicates."""
        with patch.object(AlertService, '_load_chats'):
            with patch.object(AlertService, '_save_chats') as mock_save:
                service = AlertService(bot_token="test_token")
                service._chat_ids = {12345}

                service.add_chat(12345)

                # Should not save again for duplicate
                mock_save.assert_not_called()
                assert len(service._chat_ids) == 1

    def test_remove_chat(self):
        """Test removing a chat."""
        with patch.object(AlertService, '_load_chats'):
            with patch.object(AlertService, '_save_chats'):
                service = AlertService(bot_token="test_token")
                service._chat_ids = {12345, 67890}

                service.remove_chat(12345)

                assert 12345 not in service._chat_ids
                assert 67890 in service._chat_ids

    def test_remove_nonexistent_chat(self):
        """Test removing non-existent chat does nothing."""
        with patch.object(AlertService, '_load_chats'):
            with patch.object(AlertService, '_save_chats') as mock_save:
                service = AlertService(bot_token="test_token")
                service._chat_ids = {12345}

                service.remove_chat(99999)

                mock_save.assert_not_called()
                assert 12345 in service._chat_ids

    def test_chat_count(self):
        """Test chat count property."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {1, 2, 3, 4, 5}

        assert service.chat_count == 5

    def test_load_chats_from_file(self):
        """Test loading chats from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chats_file = Path(tmpdir) / "chats.json"
            chats_file.write_text(json.dumps({"chat_ids": [111, 222, 333]}))

            with patch('services.alert_service.CHATS_FILE', chats_file):
                service = AlertService(bot_token="test_token")

            assert 111 in service._chat_ids
            assert 222 in service._chat_ids
            assert 333 in service._chat_ids

    def test_load_chats_missing_file(self):
        """Test loading with missing file creates empty set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chats_file = Path(tmpdir) / "nonexistent.json"

            with patch('services.alert_service.CHATS_FILE', chats_file):
                service = AlertService(bot_token="test_token")

            assert len(service._chat_ids) == 0

    def test_save_chats_to_file(self):
        """Test saving chats to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chats_file = Path(tmpdir) / "data" / "chats.json"

            with patch('services.alert_service.CHATS_FILE', chats_file):
                with patch.object(AlertService, '_load_chats'):
                    service = AlertService(bot_token="test_token")
                    service._chat_ids = {111, 222}

                    service._save_chats()

            assert chats_file.exists()
            data = json.loads(chats_file.read_text())
            assert set(data["chat_ids"]) == {111, 222}


class TestAlertServiceKeyboard:
    """Tests for keyboard creation."""

    def test_create_keyboard_with_condition_id(self, sample_whale_trade):
        """Test keyboard creation with valid condition ID."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(
                bot_token="test_token",
                polybot_username="TestBot"
            )

            keyboard = service._create_keyboard(sample_whale_trade)

            assert keyboard is not None
            # Should have 2 rows
            assert len(keyboard.inline_keyboard) == 2
            # First row - Trade Now
            assert "Trade Now" in keyboard.inline_keyboard[0][0].text
            # Second row - View on Polymarket
            assert "Polymarket" in keyboard.inline_keyboard[1][0].text

    def test_create_keyboard_without_polybot_username(self, sample_whale_trade):
        """Test keyboard creation without PolyBot username returns None."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service.polybot_username = None

            keyboard = service._create_keyboard(sample_whale_trade)

            assert keyboard is None

    def test_create_keyboard_without_condition_id(self, sample_whale_trade):
        """Test keyboard creation without condition ID returns None."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(
                bot_token="test_token",
                polybot_username="TestBot"
            )
            sample_whale_trade.condition_id = ""

            keyboard = service._create_keyboard(sample_whale_trade)

            assert keyboard is None


class TestAlertServiceSending:
    """Tests for message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_whale_alert_no_chats(self, sample_whale_trade):
        """Test sending alert with no subscribed chats."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = set()

            result = await service.send_whale_alert(sample_whale_trade)

            assert result == 0

    @pytest.mark.asyncio
    async def test_send_whale_alert_success(self, sample_whale_trade):
        """Test successful alert sending."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {111, 222}
            service.bot = MagicMock()
            service.bot.send_message = AsyncMock()

            result = await service.send_whale_alert(sample_whale_trade)

            assert result == 2
            assert service.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_send_whale_alert_partial_failure(self, sample_whale_trade):
        """Test alert sending with some failures."""
        from telegram.error import Forbidden

        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {111, 222, 333}
            service.bot = MagicMock()

            # First succeeds, second fails with Forbidden, third succeeds
            service.bot.send_message = AsyncMock(
                side_effect=[None, Forbidden("Bot blocked"), None]
            )

            with patch.object(service, 'remove_chat') as mock_remove:
                result = await service.send_whale_alert(sample_whale_trade)

            assert result == 2
            mock_remove.assert_called_once_with(222)

    @pytest.mark.asyncio
    async def test_send_startup_message(self):
        """Test startup message sending."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {111}
            service.bot = MagicMock()
            service.bot.send_message = AsyncMock()

            result = await service.send_startup_message()

            assert result == 1
            service.bot.send_message.assert_called_once()
            call_args = service.bot.send_message.call_args
            assert "Started" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_send_shutdown_message(self):
        """Test shutdown message sending."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {111}
            service.bot = MagicMock()
            service.bot.send_message = AsyncMock()

            result = await service.send_shutdown_message()

            assert result == 1
            service.bot.send_message.assert_called_once()
            call_args = service.bot.send_message.call_args
            assert "Stopped" in call_args.kwargs["text"]


class TestAlertServiceHandlers:
    """Tests for command handlers."""

    @pytest.mark.asyncio
    async def test_handle_start_private_chat(self):
        """Test /start command in private chat."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = set()

            update = MagicMock()
            update.effective_chat.id = 12345
            update.effective_chat.type = "private"
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            with patch.object(service, 'add_chat') as mock_add:
                await service._handle_start(update, context)

            mock_add.assert_called_once_with(12345)
            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args
            assert "subscribed" in call_args.args[0].lower()

    @pytest.mark.asyncio
    async def test_handle_start_group_chat(self):
        """Test /start command in group chat."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = set()

            update = MagicMock()
            update.effective_chat.id = -12345
            update.effective_chat.type = "group"
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            with patch.object(service, 'add_chat') as mock_add:
                await service._handle_start(update, context)

            mock_add.assert_called_once_with(-12345)

    @pytest.mark.asyncio
    async def test_handle_stop(self):
        """Test /stop command."""
        with patch.object(AlertService, '_load_chats'):
            service = AlertService(bot_token="test_token")
            service._chat_ids = {12345}

            update = MagicMock()
            update.effective_chat.id = 12345
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            with patch.object(service, 'remove_chat') as mock_remove:
                await service._handle_stop(update, context)

            mock_remove.assert_called_once_with(12345)
            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args
            assert "unsubscribed" in call_args.args[0].lower()
