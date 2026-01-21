"""Auto-claim service for settled market positions.

Note: This service is simplified for the EOA wallet architecture.
Automatic claiming via relayer is not available in this version.
Users need to manually claim their winning positions through Polymarket.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from datetime import datetime

from database.connection import Database
from database.repositories import PositionRepository, WalletRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class ClaimResult:
    """Result of a claim operation."""
    success: bool
    user_id: int
    position_id: int
    amount_claimed: float
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class ClaimService:
    """
    Service for tracking settled market positions.

    Note: Automatic claiming is not available in the EOA wallet version.
    Users need to claim their winnings manually through Polymarket's interface.
    """

    def __init__(
        self,
        db: Database,
        bot_send_message: Optional[Callable] = None,
    ):
        self.db = db
        self.position_repo = PositionRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.user_repo = UserRepository(db)
        self.bot_send_message = bot_send_message

    async def handle_market_resolution(
        self,
        condition_id: str,
        winning_outcome: str,
    ) -> List[ClaimResult]:
        """
        Handle market resolution by notifying users.

        Note: In EOA mode, users must claim manually through Polymarket.

        Args:
            condition_id: Resolved market condition ID
            winning_outcome: "YES" or "NO"

        Returns:
            List of claim results (empty - no auto-claim)
        """
        results = []

        # Record resolved market
        await self._record_resolved_market(condition_id, winning_outcome)

        # Find all positions for this market
        positions = await self._get_positions_for_market(condition_id)

        if not positions:
            logger.info(f"No positions found for resolved market {condition_id[:16]}...")
            return results

        logger.info(
            f"Processing {len(positions)} positions for resolved market "
            f"{condition_id[:16]}... (winner: {winning_outcome})"
        )

        for position in positions:
            if position["outcome"] == winning_outcome:
                # Winning position - notify user to claim manually
                await self._notify_user_winner(position, winning_outcome)
            else:
                # Losing position - mark as settled
                await self._close_losing_position(position)
                await self._notify_user_loss(position)

        # Mark market as processed
        await self._mark_market_processed(condition_id)

        return results

    async def _get_positions_for_market(
        self,
        condition_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all positions for a market."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT p.*, w.address as wallet_address
            FROM positions p
            JOIN wallets w ON p.user_id = w.user_id
            WHERE p.market_condition_id = ? AND p.size > 0
            """,
            (condition_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def _close_losing_position(
        self,
        position: Dict[str, Any],
    ) -> None:
        """Close a losing position with realized loss."""
        conn = await self.db.get_connection()
        loss = -(position["size"] * position["average_entry_price"])

        await conn.execute(
            """
            UPDATE positions
            SET size = 0,
                realized_pnl = realized_pnl + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (loss, datetime.utcnow(), position["id"]),
        )
        await conn.commit()

        logger.info(
            f"Position {position['id']} closed as loss: ${abs(loss):.2f}"
        )

    async def _record_resolved_market(
        self,
        condition_id: str,
        winning_outcome: str,
    ) -> None:
        """Record resolved market in cache."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT OR IGNORE INTO resolved_markets
            (condition_id, winning_outcome, resolved_at, processed)
            VALUES (?, ?, ?, 0)
            """,
            (condition_id, winning_outcome, datetime.utcnow()),
        )
        await conn.commit()

    async def _mark_market_processed(
        self,
        condition_id: str,
    ) -> None:
        """Mark market as processed."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE resolved_markets
            SET processed = 1
            WHERE condition_id = ?
            """,
            (condition_id,),
        )
        await conn.commit()

    async def _notify_user_winner(
        self,
        position: Dict[str, Any],
        winning_outcome: str,
    ) -> None:
        """Send notification to user about winning position - needs manual claim."""
        if not self.bot_send_message:
            return

        try:
            user = await self.user_repo.get_by_id(position["user_id"])
            if user:
                market_question = position.get("market_question", "Unknown Market")
                if len(market_question) > 50:
                    market_question = market_question[:50] + "..."

                claim_amount = position["size"]

                await self.bot_send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"🎉 *You Won!*\n\n"
                        f"📊 Market: _{market_question}_\n"
                        f"✅ Outcome: *{position['outcome']}* (Winner)\n"
                        f"💰 Winnings: *${claim_amount:.2f}*\n\n"
                        f"⚠️ Please claim your winnings manually at:\n"
                        f"[polymarket.com/portfolio](https://polymarket.com/portfolio)"
                    ),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to notify user about win: {e}")

    async def _notify_user_loss(
        self,
        position: Dict[str, Any],
    ) -> None:
        """Send notification to user about losing position."""
        if not self.bot_send_message:
            return

        try:
            user = await self.user_repo.get_by_id(position["user_id"])
            if user:
                market_question = position.get("market_question", "Unknown Market")
                if len(market_question) > 50:
                    market_question = market_question[:50] + "..."

                loss = position["size"] * position["average_entry_price"]

                await self.bot_send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"📉 *Position Settled*\n\n"
                        f"📊 Market: _{market_question}_\n"
                        f"❌ Outcome: *{position['outcome']}* (Did not win)\n"
                        f"💸 Loss: *${abs(loss):.2f}*\n\n"
                        f"The position has been closed."
                    ),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to notify user about loss: {e}")

    async def manual_claim(
        self,
        user_id: int,
        position_id: int,
    ) -> ClaimResult:
        """
        Manual claim is not supported in EOA mode.

        Users should claim through Polymarket directly.
        """
        return ClaimResult(
            success=False,
            user_id=user_id,
            position_id=position_id,
            amount_claimed=0,
            error="Auto-claim not available. Please claim at polymarket.com/portfolio",
        )

    async def get_pending_claims(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending claims for a user (not used in EOA mode)."""
        return []

    async def retry_pending_claims(self) -> List[ClaimResult]:
        """Retry pending claims (not used in EOA mode)."""
        return []

    async def close(self):
        """Clean up resources."""
        pass
