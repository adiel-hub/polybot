"""Tests for trading modes (Standard, Fast, Ludicrous)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import ContextTypes

from bot.handlers.trading import handle_amount_input, confirm_order
from bot.conversations.states import ConversationState
from database.models.user import User as DBUser


@pytest.fixture
def mock_update():
    """Create a mock Update object with message."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123456
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.text = "50"
    update.callback_query = None
    return update


@pytest.fixture
def mock_callback_update():
    """Create a mock Update object with callback query."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123456
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = "order_confirm"
    update.message = None
    return update


@pytest.fixture
def mock_context():
    """Create a mock context with required services."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        "current_market": {
            "condition_id": "test_condition_id",
            "question": "Test Market Question",
            "yes_price": 0.6,
            "no_price": 0.4,
        },
        "order_type": "MARKET",
        "outcome": "YES",
        "token_id": "test_token_id",
    }

    # Mock user service
    user_service = MagicMock()
    user_service.get_user = AsyncMock()
    user_service.get_user_settings = AsyncMock()

    # Mock trading service
    trading_service = MagicMock()
    trading_service.place_order = AsyncMock()

    # Mock wallet repo
    wallet_repo = MagicMock()
    wallet_repo.get_by_user_id = AsyncMock()

    context.bot_data = {
        "user_service": user_service,
        "trading_service": trading_service,
        "wallet_repo": wallet_repo,
        "db": MagicMock(),
    }

    return context


@pytest.fixture
def mock_db_user():
    """Create a mock database user."""
    user = MagicMock(spec=DBUser)
    user.id = 1
    user.telegram_id = 123456
    return user


class TestStandardMode:
    """Tests for Standard trading mode (always confirm)."""

    @pytest.mark.asyncio
    async def test_standard_mode_always_shows_confirmation(
        self, mock_update, mock_context, mock_db_user
    ):
        """Standard mode should always show confirmation regardless of amount."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "standard",
            "fast_mode_threshold": 100.0,
        }

        # Test with small amount
        mock_update.message.text = "10"
        result = await handle_amount_input(mock_update, mock_context)

        # Should show confirmation
        assert result == ConversationState.CONFIRM_ORDER
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "📋 *Confirm Order*" in call_args[0][0]
        assert "✅ Confirm this order?" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_standard_mode_large_amount(
        self, mock_update, mock_context, mock_db_user
    ):
        """Standard mode shows confirmation even for large amounts."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "standard",
            "fast_mode_threshold": 100.0,
        }

        # Test with large amount
        mock_update.message.text = "500"
        result = await handle_amount_input(mock_update, mock_context)

        # Should show confirmation
        assert result == ConversationState.CONFIRM_ORDER
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "📋 *Confirm Order*" in call_args[0][0]


class TestFastMode:
    """Tests for Fast trading mode (threshold-based)."""

    @pytest.mark.asyncio
    async def test_fast_mode_below_threshold_executes_immediately(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should execute immediately when amount is below threshold."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with amount below threshold
            mock_update.message.text = "50"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately
            assert mock_context.bot_data["trading_service"].place_order.called
            # Should show fast mode message
            calls = [str(call) for call in mock_update.message.reply_text.call_args_list]
            message_text = " ".join(calls)
            assert "Fast Mode" in message_text or "⚡" in message_text

    @pytest.mark.asyncio
    async def test_fast_mode_above_threshold_shows_confirmation(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should show confirmation when amount is above threshold."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }

        # Test with amount above threshold
        mock_update.message.text = "150"
        result = await handle_amount_input(mock_update, mock_context)

        # Should show confirmation
        assert result == ConversationState.CONFIRM_ORDER
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "📋 *Confirm Order*" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_fast_mode_at_threshold_executes_immediately(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should execute immediately when amount equals threshold (<=)."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with amount exactly at threshold
            mock_update.message.text = "100"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately (threshold is >, so = executes)
            assert mock_context.bot_data["trading_service"].place_order.called

    @pytest.mark.asyncio
    async def test_fast_mode_just_below_threshold_executes(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should execute when amount is just below threshold."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with amount just below threshold (99.99)
            mock_update.message.text = "99.99"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately
            assert mock_context.bot_data["trading_service"].place_order.called


class TestLudicrousMode:
    """Tests for Ludicrous trading mode (always execute immediately)."""

    @pytest.mark.asyncio
    async def test_ludicrous_mode_small_amount_executes_immediately(
        self, mock_update, mock_context, mock_db_user
    ):
        """Ludicrous mode should execute immediately for small amounts."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "ludicrous",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with small amount
            mock_update.message.text = "10"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately
            assert mock_context.bot_data["trading_service"].place_order.called
            # Should show ludicrous mode message
            calls = [str(call) for call in mock_update.message.reply_text.call_args_list]
            message_text = " ".join(calls)
            assert "Ludicrous Mode" in message_text or "🚀" in message_text

    @pytest.mark.asyncio
    async def test_ludicrous_mode_large_amount_executes_immediately(
        self, mock_update, mock_context, mock_db_user
    ):
        """Ludicrous mode should execute immediately even for large amounts."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "ludicrous",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with large amount (well above threshold)
            mock_update.message.text = "1000"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately (no confirmation)
            assert mock_context.bot_data["trading_service"].place_order.called

    @pytest.mark.asyncio
    async def test_ludicrous_mode_ignores_threshold(
        self, mock_update, mock_context, mock_db_user
    ):
        """Ludicrous mode should ignore threshold completely."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "ludicrous",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with amount at threshold
            mock_update.message.text = "100"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately (threshold doesn't matter)
            assert mock_context.bot_data["trading_service"].place_order.called


class TestOrderConfirmation:
    """Tests for the confirmation flow."""

    @pytest.mark.asyncio
    async def test_confirm_order_executes_successfully(
        self, mock_callback_update, mock_context, mock_db_user
    ):
        """Confirming an order should execute it successfully."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }
        mock_context.user_data["amount"] = 50

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            result = await confirm_order(mock_callback_update, mock_context)

            # Should call trading service
            assert mock_context.bot_data["trading_service"].place_order.called
            # Should show success message
            mock_callback_update.callback_query.edit_message_text.assert_called()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_missing_user_settings_defaults_to_standard(
        self, mock_update, mock_context, mock_db_user
    ):
        """Missing settings should default to standard mode (safest)."""
        # Setup - return empty settings
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {}

        # Test
        mock_update.message.text = "50"
        result = await handle_amount_input(mock_update, mock_context)

        # Should default to standard mode (show confirmation)
        assert result == ConversationState.CONFIRM_ORDER

    @pytest.mark.asyncio
    async def test_invalid_trading_mode_defaults_to_standard(
        self, mock_update, mock_context, mock_db_user
    ):
        """Invalid trading mode should default to standard mode (safest behavior)."""
        # Setup - invalid mode
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "invalid_mode",
            "fast_mode_threshold": 100.0,
        }

        # Test
        mock_update.message.text = "50"
        result = await handle_amount_input(mock_update, mock_context)

        # Should default to standard mode (show confirmation for safety)
        assert result == ConversationState.CONFIRM_ORDER
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "📋 *Confirm Order*" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_immediate_execution_handles_order_failure(
        self, mock_update, mock_context, mock_db_user
    ):
        """Immediate execution should handle order failures gracefully."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "ludicrous",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": False,
            "error": "Insufficient balance",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            mock_update.message.text = "50"
            result = await handle_amount_input(mock_update, mock_context)

            # Should show error message
            calls = [str(call) for call in mock_update.message.reply_text.call_args_list]
            message_text = " ".join(calls)
            assert "Failed" in message_text or "❌" in message_text

    @pytest.mark.asyncio
    async def test_very_small_amount(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should handle very small amounts correctly."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }
        mock_context.bot_data["trading_service"].place_order.return_value = {
            "success": True,
            "order_id": "test_order_123",
            "status": "FILLED",
        }

        # Mock show_main_menu
        with patch("bot.handlers.trading.show_main_menu", new=AsyncMock()):
            # Test with very small amount
            mock_update.message.text = "0.01"
            result = await handle_amount_input(mock_update, mock_context)

            # Should execute immediately
            assert mock_context.bot_data["trading_service"].place_order.called

    @pytest.mark.asyncio
    async def test_very_large_amount_fast_mode(
        self, mock_update, mock_context, mock_db_user
    ):
        """Fast mode should show confirmation for very large amounts."""
        # Setup
        mock_context.bot_data["user_service"].get_user.return_value = mock_db_user
        mock_context.bot_data["user_service"].get_user_settings.return_value = {
            "trading_mode": "fast",
            "fast_mode_threshold": 100.0,
        }

        # Test with very large amount
        mock_update.message.text = "10000"
        result = await handle_amount_input(mock_update, mock_context)

        # Should show confirmation
        assert result == ConversationState.CONFIRM_ORDER
