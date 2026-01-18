"""Order fill subscriber for monitoring limit order fills and collecting commissions."""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Set

from database.connection import Database
from database.repositories import OrderRepository, WalletRepository, PositionRepository
from services.commission_service import CommissionService
from core.wallet import KeyEncryption
from core.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)


class OrderFillSubscriber:
    """
    Subscribes to Polymarket user channel to monitor limit order fills.

    When a limit order is filled, automatically collects operator commission.
    This ensures commissions are collected even for orders that fill later.
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        db: Database,
        encryption: KeyEncryption,
        user_ws_url: str,
        bot_send_message: Optional[Callable] = None,
    ):
        self.ws_manager = ws_manager
        self.db = db
        self.encryption = encryption
        self.user_ws_url = user_ws_url
        self.bot_send_message = bot_send_message

        # Repositories
        self.order_repo = OrderRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.position_repo = PositionRepository(db)

        # Commission service
        self.commission_service = CommissionService(db)

        # Track monitored order IDs (Polymarket order IDs)
        self._monitored_orders: Dict[str, Dict] = {}  # polymarket_order_id -> order info
        # Track processed fills to avoid duplicates
        self._processed_fills: Set[str] = set()

    async def start(self) -> None:
        """Start the order fill subscriber."""
        # Note: We share the "polymarket_user" connection with CopyTradeSubscriber
        # The WebSocket manager will call our handler for user channel messages

        # Load open orders to monitor
        await self._refresh_monitored_orders()
        logger.info("Order fill subscriber started")

    async def _refresh_monitored_orders(self) -> None:
        """Load all open limit orders that need monitoring."""
        try:
            conn = await self.db.get_connection()

            # Get all open/pending orders that haven't been commission-processed
            cursor = await conn.execute(
                """
                SELECT o.*, w.address as wallet_address, w.encrypted_private_key, w.encryption_salt
                FROM orders o
                JOIN wallets w ON w.user_id = o.user_id
                WHERE o.status IN ('OPEN', 'PENDING', 'PARTIALLY_FILLED')
                AND o.order_type = 'LIMIT'
                AND o.polymarket_order_id IS NOT NULL
                AND o.id NOT IN (SELECT order_id FROM operator_commissions)
                """
            )
            rows = await cursor.fetchall()

            self._monitored_orders.clear()

            for row in rows:
                order_data = dict(row)
                polymarket_id = order_data.get("polymarket_order_id")
                if polymarket_id:
                    self._monitored_orders[polymarket_id] = order_data

            logger.info(f"Monitoring {len(self._monitored_orders)} open limit orders for fills")

        except Exception as e:
            logger.error(f"Failed to refresh monitored orders: {e}")

    async def add_order_to_monitor(self, order_id: int, polymarket_order_id: str) -> None:
        """Add a new limit order to monitoring."""
        try:
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                """
                SELECT o.*, w.address as wallet_address, w.encrypted_private_key, w.encryption_salt
                FROM orders o
                JOIN wallets w ON w.user_id = o.user_id
                WHERE o.id = ?
                """,
                (order_id,)
            )
            row = await cursor.fetchone()

            if row:
                order_data = dict(row)
                self._monitored_orders[polymarket_order_id] = order_data
                logger.debug(f"Added order {polymarket_order_id} to fill monitoring")

        except Exception as e:
            logger.error(f"Failed to add order to monitoring: {e}")

    async def remove_order_from_monitor(self, polymarket_order_id: str) -> None:
        """Remove an order from monitoring (cancelled or already processed)."""
        if polymarket_order_id in self._monitored_orders:
            del self._monitored_orders[polymarket_order_id]
            logger.debug(f"Removed order {polymarket_order_id} from fill monitoring")

    async def handle_user_message(
        self,
        connection_name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Handle incoming user WebSocket messages.

        This is called by the WebSocket manager for user channel messages.
        """
        event_type = data.get("event_type") or data.get("type")

        # Handle order fill events
        if event_type in ("order_filled", "fill", "trade", "order_update"):
            await self._handle_order_update(data)

    async def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Process an order update/fill event."""
        try:
            # Extract order ID
            order_id = (
                data.get("order_id") or
                data.get("orderId") or
                data.get("id")
            )
            status = (
                data.get("status") or
                data.get("order_status") or
                ""
            ).upper()

            if not order_id:
                return

            # Check if this is a monitored order
            if order_id not in self._monitored_orders:
                return

            # Check if it's a fill event
            if status not in ("FILLED", "MATCHED"):
                # Also check for fill-related event types
                event_type = (data.get("event_type") or data.get("type") or "").lower()
                if event_type not in ("fill", "order_filled", "trade"):
                    return

            # Skip if already processed
            fill_id = f"{order_id}_{status}"
            if fill_id in self._processed_fills:
                return

            self._processed_fills.add(fill_id)
            # Keep processed set bounded
            if len(self._processed_fills) > 10000:
                self._processed_fills = set(list(self._processed_fills)[-5000:])

            logger.info(f"Limit order filled: {order_id}")

            # Get order details
            order_data = self._monitored_orders[order_id]

            # Calculate filled amount
            filled_size = float(data.get("filled_size") or data.get("size") or order_data.get("size", 0))
            price = float(data.get("price") or order_data.get("price", 0))

            # For limit orders, the trade amount is size * price
            trade_amount = filled_size * price if price > 0 else filled_size

            # Process commission
            await self._process_fill_commission(order_data, trade_amount)

            # Update local order status
            db_order_id = order_data.get("id")
            if db_order_id:
                await self.order_repo.update_status(db_order_id, "FILLED")

            # Remove from monitoring
            await self.remove_order_from_monitor(order_id)

            # Notify user
            if self.bot_send_message:
                user_id = order_data.get("user_id")
                if user_id:
                    await self._notify_user_fill(user_id, order_data, trade_amount)

        except Exception as e:
            logger.error(f"Failed to handle order update: {e}")

    async def _process_fill_commission(
        self,
        order_data: Dict[str, Any],
        trade_amount: float,
    ) -> None:
        """Process commission for a filled limit order."""
        try:
            # Check if commission is enabled
            if not self.commission_service.is_enabled():
                return

            # Calculate commission
            commission_calc = self.commission_service.calculate_commission(trade_amount)

            if commission_calc.commission_amount <= 0:
                logger.debug(f"Commission below minimum for ${trade_amount:.2f} limit order")
                return

            user_id = order_data.get("user_id")
            db_order_id = order_data.get("id")
            side = order_data.get("side", "BUY")

            logger.info(
                f"Processing commission for filled limit order: "
                f"${commission_calc.commission_amount:.4f} on ${trade_amount:.2f} {side}"
            )

            # Decrypt wallet for transfer
            try:
                private_key = self.encryption.decrypt(
                    order_data.get("encrypted_private_key"),
                    order_data.get("encryption_salt"),
                )
            except Exception as e:
                logger.error(f"Failed to decrypt wallet for commission: {e}")
                # Record pending commission for manual processing
                await self.commission_service.record_commission(
                    user_id=user_id,
                    order_id=db_order_id,
                    trade_type=side,
                    calculation=commission_calc,
                    status="PENDING",
                )
                return

            # Transfer commission
            transfer_result = await self.commission_service.transfer_commission(
                from_private_key=private_key,
                amount=commission_calc.commission_amount,
            )

            if transfer_result.success:
                await self.commission_service.record_commission(
                    user_id=user_id,
                    order_id=db_order_id,
                    trade_type=side,
                    calculation=commission_calc,
                    tx_hash=transfer_result.tx_hash,
                    status="TRANSFERRED",
                )
                logger.info(
                    f"Limit order commission transferred: "
                    f"${commission_calc.commission_amount:.4f} TX: {transfer_result.tx_hash}"
                )
            else:
                await self.commission_service.record_commission(
                    user_id=user_id,
                    order_id=db_order_id,
                    trade_type=side,
                    calculation=commission_calc,
                    status="PENDING",
                )
                logger.warning(
                    f"Limit order commission transfer failed: {transfer_result.error}"
                )

        except Exception as e:
            logger.error(f"Failed to process fill commission: {e}")

    async def _notify_user_fill(
        self,
        user_id: int,
        order_data: Dict[str, Any],
        trade_amount: float,
    ) -> None:
        """Notify user that their limit order was filled."""
        try:
            # Get user's Telegram ID
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                "SELECT telegram_id FROM users WHERE id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return

            telegram_id = row["telegram_id"]
            market_question = order_data.get("market_question", "Unknown Market")
            outcome = order_data.get("outcome", "")
            side = order_data.get("side", "BUY")

            # Truncate question if too long
            if len(market_question) > 50:
                market_question = market_question[:47] + "..."

            message = (
                f"✅ *Limit Order Filled!*\n\n"
                f"📊 {market_question}\n"
                f"📈 {side} {outcome}\n"
                f"💵 Amount: `${trade_amount:.2f}`\n\n"
                f"Your order has been executed."
            )

            await self.bot_send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Failed to notify user of fill: {e}")

    async def check_pending_commissions(self) -> None:
        """Check and retry pending commission transfers."""
        try:
            pending = await self.commission_service.get_pending_commissions()

            for commission in pending:
                try:
                    # Get wallet info
                    user_id = commission["user_id"]
                    wallet = await self.wallet_repo.get_by_user_id(user_id)

                    if not wallet:
                        continue

                    # Decrypt key
                    private_key = self.encryption.decrypt(
                        wallet.encrypted_private_key,
                        wallet.encryption_salt,
                    )

                    # Retry transfer
                    result = await self.commission_service.transfer_commission(
                        from_private_key=private_key,
                        amount=commission["commission_amount"],
                    )

                    if result.success:
                        await self.commission_service.update_commission_status(
                            commission["id"],
                            "TRANSFERRED",
                            tx_hash=result.tx_hash,
                        )
                        logger.info(f"Retried commission transfer successful: {result.tx_hash}")
                    else:
                        logger.warning(f"Retry commission transfer failed: {result.error}")

                except Exception as e:
                    logger.error(f"Failed to retry commission {commission['id']}: {e}")

        except Exception as e:
            logger.error(f"Failed to check pending commissions: {e}")
