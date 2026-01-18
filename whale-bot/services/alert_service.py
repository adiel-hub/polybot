"""Telegram alert service for whale notifications."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional, Set, Tuple

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, POLYBOT_USERNAME, WHALE_CHANNEL_ID
from monitors.whale_monitor import WhaleTrade
from utils.formatting import format_whale_alert, create_deep_link

logger = logging.getLogger(__name__)

# Rate limiting settings
MIN_MESSAGE_INTERVAL = 20  # seconds between messages

# File to persist chat IDs
CHATS_FILE = Path(__file__).parent.parent / "data" / "chats.json"


class AlertService:
    """Service for sending whale alerts to all subscribed Telegram chats."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        polybot_username: Optional[str] = None,
    ):
        """
        Initialize the alert service.

        Args:
            bot_token: Telegram bot token (defaults to config)
            polybot_username: PolyBot username for deep links
        """
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.polybot_username = polybot_username or POLYBOT_USERNAME
        self.bot = Bot(token=self.bot_token)
        self.application: Optional[Application] = None

        # Set of chat IDs to broadcast to
        self._chat_ids: Set[int] = set()
        self._load_chats()

        # Rate limiting queue
        self._alert_queue: asyncio.Queue[WhaleTrade] = asyncio.Queue()
        self._last_send_time: float = 0
        self._queue_processor_task: Optional[asyncio.Task] = None

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

    def _load_chats(self) -> None:
        """Load saved chat IDs from file and env config."""
        try:
            if CHATS_FILE.exists():
                with open(CHATS_FILE, "r") as f:
                    data = json.load(f)
                    self._chat_ids = set(data.get("chat_ids", []))
                logger.info(f"Loaded {len(self._chat_ids)} chats from file")
        except Exception as e:
            logger.error(f"Failed to load chats: {e}")
            self._chat_ids = set()

        # Add pre-configured channel from env if set
        if WHALE_CHANNEL_ID:
            try:
                channel_id = int(WHALE_CHANNEL_ID)
                if channel_id not in self._chat_ids:
                    self._chat_ids.add(channel_id)
                    logger.info(f"Added pre-configured channel {channel_id}")
            except ValueError:
                logger.error(f"Invalid WHALE_CHANNEL_ID: {WHALE_CHANNEL_ID}")

    def _save_chats(self) -> None:
        """Save chat IDs to file."""
        try:
            CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CHATS_FILE, "w") as f:
                json.dump({"chat_ids": list(self._chat_ids)}, f)
        except Exception as e:
            logger.error(f"Failed to save chats: {e}")

    def add_chat(self, chat_id: int) -> None:
        """Add a chat to broadcast list."""
        if chat_id not in self._chat_ids:
            self._chat_ids.add(chat_id)
            self._save_chats()
            logger.info(f"Added chat {chat_id} to broadcast list")

    def remove_chat(self, chat_id: int) -> None:
        """Remove a chat from broadcast list."""
        if chat_id in self._chat_ids:
            self._chat_ids.discard(chat_id)
            self._save_chats()
            logger.info(f"Removed chat {chat_id} from broadcast list")

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command - register chat for alerts."""
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        self.add_chat(chat_id)

        from config import WHALE_THRESHOLD

        if chat_type == "private":
            message = (
                "🐋 *Whale Alert Bot*\n\n"
                f"✅ You're now subscribed to whale alerts!\n\n"
                f"📊 You'll receive notifications for trades ≥ ${WHALE_THRESHOLD:,.0f}\n\n"
                "Use /stop to unsubscribe."
            )
        else:
            message = (
                "🐋 *Whale Alert Bot Activated*\n\n"
                f"✅ This chat is now subscribed to whale alerts!\n\n"
                f"📊 Notifications for trades ≥ ${WHALE_THRESHOLD:,.0f}\n\n"
                "Use /stop to unsubscribe."
            )

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def _handle_stop(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /stop command - unregister chat from alerts."""
        chat_id = update.effective_chat.id
        self.remove_chat(chat_id)

        await update.message.reply_text(
            "🔴 *Unsubscribed from whale alerts*\n\n"
            "Use /start to subscribe again.",
            parse_mode=ParseMode.MARKDOWN,
        )

    def _create_keyboard(self, trade: WhaleTrade) -> Optional[InlineKeyboardMarkup]:
        """Create inline keyboard with Trade Now button."""
        if not self.polybot_username or not trade.condition_id:
            return None

        import re

        deep_link = create_deep_link(trade.condition_id, self.polybot_username)

        # Clean the market slug - remove trailing numeric patterns (token IDs)
        polymarket_url = "https://polymarket.com"
        if trade.market_slug:
            clean_slug = re.sub(r'(-\d+)+$', '', trade.market_slug)
            if clean_slug:
                polymarket_url = f"https://polymarket.com/market/{clean_slug}"

        keyboard = [
            [
                InlineKeyboardButton(
                    text="📈 Trade Now",
                    url=deep_link,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 View on Polymarket",
                    url=polymarket_url,
                )
            ],
        ]

        # Add Polygonscan link if transaction hash is available
        if trade.tx_hash:
            keyboard.append([
                InlineKeyboardButton(
                    text="🔍 View on Polygonscan",
                    url=f"https://polygonscan.com/tx/{trade.tx_hash}",
                )
            ])

        return InlineKeyboardMarkup(keyboard)

    async def queue_whale_alert(self, trade: WhaleTrade) -> None:
        """
        Queue a whale alert for rate-limited sending.

        Args:
            trade: The whale trade to alert about
        """
        await self._alert_queue.put(trade)
        queue_size = self._alert_queue.qsize()
        logger.info(
            f"Queued alert for ${trade.value:,.2f} on {trade.market_title[:30]}... "
            f"(queue size: {queue_size})"
        )

    async def start_queue_processor(self) -> None:
        """Start the background queue processor."""
        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue())
            logger.info("Started alert queue processor")

    async def stop_queue_processor(self) -> None:
        """Stop the background queue processor."""
        if self._queue_processor_task and not self._queue_processor_task.done():
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped alert queue processor")

    async def _process_queue(self) -> None:
        """Background task that processes the alert queue with rate limiting."""
        logger.info("Alert queue processor started")
        while True:
            try:
                # Wait for next trade in queue
                trade = await self._alert_queue.get()

                # Calculate wait time for rate limiting
                now = time.time()
                time_since_last = now - self._last_send_time
                if time_since_last < MIN_MESSAGE_INTERVAL:
                    wait_time = MIN_MESSAGE_INTERVAL - time_since_last
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s before sending")
                    await asyncio.sleep(wait_time)

                # Send the alert
                await self._send_whale_alert_immediate(trade)
                self._last_send_time = time.time()

                # Mark task as done
                self._alert_queue.task_done()

            except asyncio.CancelledError:
                logger.info("Alert queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    async def _send_whale_alert_immediate(self, trade: WhaleTrade) -> int:
        """
        Send a whale alert immediately to all subscribed chats.

        Args:
            trade: The whale trade to alert about

        Returns:
            Number of chats successfully notified
        """
        if not self._chat_ids:
            logger.warning("No chats to send alerts to")
            return 0

        message = format_whale_alert(trade, self.polybot_username)
        keyboard = self._create_keyboard(trade)

        success_count = 0
        failed_chats = []

        for chat_id in list(self._chat_ids):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                success_count += 1

            except Forbidden:
                # Bot was blocked or removed from chat
                logger.warning(f"Bot removed from chat {chat_id}, removing from list")
                failed_chats.append(chat_id)

            except TelegramError as e:
                logger.error(f"Failed to send to chat {chat_id}: {e}")

            except Exception as e:
                logger.error(f"Unexpected error for chat {chat_id}: {e}")

        # Remove chats where bot was blocked
        for chat_id in failed_chats:
            self.remove_chat(chat_id)

        logger.info(
            f"Alert sent to {success_count}/{len(self._chat_ids)} chats: "
            f"${trade.value:,.2f} on {trade.market_title[:30]}..."
        )
        return success_count

    async def send_whale_alert(self, trade: WhaleTrade) -> int:
        """
        Queue a whale alert for rate-limited sending.
        This is the main entry point - alerts go through the queue.

        Args:
            trade: The whale trade to alert about

        Returns:
            0 (actual send count comes from queue processor)
        """
        await self.queue_whale_alert(trade)
        return 0  # Actual count comes later via queue

    async def send_startup_message(self) -> int:
        """Send startup notification to all chats."""
        if not self._chat_ids:
            return 0

        from config import WHALE_THRESHOLD

        message = (
            "🐋 *Whale Alert Bot Started*\n\n"
            f"📊 Monitoring Polymarket for trades ≥ ${WHALE_THRESHOLD:,.0f}\n"
            "🔔 Stay tuned for whale activity!"
        )

        success_count = 0
        for chat_id in list(self._chat_ids):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send startup to {chat_id}: {e}")

        return success_count

    async def send_shutdown_message(self) -> int:
        """Send shutdown notification to all chats."""
        if not self._chat_ids:
            return 0

        message = "🔴 *Whale Alert Bot Stopped*"

        success_count = 0
        for chat_id in list(self._chat_ids):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
                success_count += 1
            except Exception:
                pass  # Ignore errors on shutdown

        return success_count

    def setup_handlers(self, application: Application) -> None:
        """Setup command handlers for the bot."""
        self.application = application
        application.add_handler(CommandHandler("start", self._handle_start))
        application.add_handler(CommandHandler("stop", self._handle_stop))

    @property
    def chat_count(self) -> int:
        """Return number of subscribed chats."""
        return len(self._chat_ids)
