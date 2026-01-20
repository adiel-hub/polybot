"""Auto-claim service for settled market positions."""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from database.connection import Database
from database.repositories import PositionRepository, WalletRepository, UserRepository
from core.polymarket import PolymarketRelayer

logger = logging.getLogger(__name__)

# Retry settings
MAX_RETRY_COUNT = 5
RETRY_INTERVAL_HOURS = 1


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
    Service for claiming winning positions after market resolution.

    Uses Polymarket relayer for gasless redemption.
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
        self.relayer = PolymarketRelayer()
        self.bot_send_message = bot_send_message

    async def handle_market_resolution(
        self,
        condition_id: str,
        winning_outcome: str,
    ) -> List[ClaimResult]:
        """
        Handle market resolution by claiming all winning positions.

        Args:
            condition_id: Resolved market condition ID
            winning_outcome: "YES" or "NO"

        Returns:
            List of claim results
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
                # Winning position - claim it
                result = await self._claim_position(position, winning_outcome)
                results.append(result)

                # Record claim attempt
                await self._record_claim(result, condition_id, winning_outcome)

                if result.success:
                    await self._notify_user_claim(result, position)
                else:
                    # Schedule for retry
                    await self._schedule_retry(result, condition_id, winning_outcome)
            else:
                # Losing position - mark as settled with 0 value
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

    async def _claim_position(
        self,
        position: Dict[str, Any],
        winning_outcome: str,
    ) -> ClaimResult:
        """Claim a single winning position via relayer."""
        try:
            if not self.relayer.is_configured():
                return ClaimResult(
                    success=False,
                    user_id=position["user_id"],
                    position_id=position["id"],
                    amount_claimed=0,
                    error="Relayer not configured - missing builder credentials",
                )

            # Calculate claim amount (position size * $1 = winning value)
            claim_amount = position["size"]  # 1 share = $1 on winning outcome

            # Determine index sets based on outcome
            # YES = index 1, NO = index 2 in Polymarket CTF
            index_set = 1 if winning_outcome == "YES" else 2

            logger.info(
                f"Claiming position {position['id']} for user {position['user_id']}: "
                f"${claim_amount:.2f} ({winning_outcome})"
            )

            # Execute claim via relayer
            result = await self.relayer.redeem_positions(
                user_address=position["wallet_address"],
                condition_id=position["market_condition_id"],
                index_sets=[index_set],
            )

            if result.success:
                # Update position as claimed
                await self._mark_position_claimed(
                    position["id"],
                    claim_amount,
                    result.tx_hash,
                )

                # Add USDC to wallet balance
                wallet = await self.wallet_repo.get_by_user_id(position["user_id"])
                if wallet:
                    await self.wallet_repo.add_balance(wallet.id, claim_amount)

                logger.info(
                    f"Position {position['id']} claimed successfully: "
                    f"${claim_amount:.2f} TX: {result.tx_hash}"
                )

                return ClaimResult(
                    success=True,
                    user_id=position["user_id"],
                    position_id=position["id"],
                    amount_claimed=claim_amount,
                    tx_hash=result.tx_hash,
                )
            else:
                logger.error(
                    f"Position {position['id']} claim failed: {result.error}"
                )
                return ClaimResult(
                    success=False,
                    user_id=position["user_id"],
                    position_id=position["id"],
                    amount_claimed=0,
                    error=result.error,
                )

        except Exception as e:
            logger.error(f"Claim position failed: {e}")
            return ClaimResult(
                success=False,
                user_id=position["user_id"],
                position_id=position["id"],
                amount_claimed=0,
                error=str(e),
            )

    async def _mark_position_claimed(
        self,
        position_id: int,
        amount: float,
        tx_hash: str,
    ) -> None:
        """Mark position as claimed and closed."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE positions
            SET size = 0,
                realized_pnl = realized_pnl + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (amount, datetime.utcnow(), position_id),
        )
        await conn.commit()

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

    async def _record_claim(
        self,
        result: ClaimResult,
        condition_id: str,
        winning_outcome: str,
    ) -> int:
        """Record claim in claims table."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO position_claims
            (user_id, position_id, market_condition_id, winning_outcome,
             amount_claimed, tx_hash, status, claimed_at, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.user_id,
                result.position_id,
                condition_id,
                winning_outcome,
                result.amount_claimed,
                result.tx_hash,
                "CLAIMED" if result.success else "PENDING",
                datetime.utcnow(),
                0,
            ),
        )
        await conn.commit()
        return cursor.lastrowid

    async def _schedule_retry(
        self,
        result: ClaimResult,
        condition_id: str,
        winning_outcome: str,
    ) -> None:
        """Schedule failed claim for retry."""
        next_retry = datetime.utcnow() + timedelta(hours=RETRY_INTERVAL_HOURS)

        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE position_claims
            SET next_retry_at = ?, error_message = ?
            WHERE position_id = ? AND status = 'PENDING'
            """,
            (next_retry, result.error, result.position_id),
        )
        await conn.commit()

        logger.info(
            f"Claim for position {result.position_id} scheduled for retry at {next_retry}"
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

    async def _notify_user_claim(
        self,
        result: ClaimResult,
        position: Dict[str, Any],
    ) -> None:
        """Send notification to user about successful claim."""
        if not self.bot_send_message:
            return

        try:
            user = await self.user_repo.get_by_id(result.user_id)
            if user:
                market_question = position.get("market_question", "Unknown Market")
                if len(market_question) > 50:
                    market_question = market_question[:50] + "..."

                await self.bot_send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"🎉 *Winning Position Claimed!*\n\n"
                        f"📊 Market: _{market_question}_\n"
                        f"✅ Outcome: *{position['outcome']}* (Winner)\n"
                        f"💰 Amount: *${result.amount_claimed:.2f}*\n\n"
                        f"The funds have been added to your wallet balance."
                    ),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to notify user about claim: {e}")

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
        Manually trigger claim for a position.

        Called from user interface when auto-claim fails or for retry.

        Args:
            user_id: User ID
            position_id: Position ID to claim

        Returns:
            ClaimResult
        """
        position = await self.position_repo.get_by_id(position_id)
        if not position or position.user_id != user_id:
            return ClaimResult(
                success=False,
                user_id=user_id,
                position_id=position_id,
                amount_claimed=0,
                error="Position not found",
            )

        # Check if position is on a resolved market
        resolved = await self._get_resolved_market(position.market_condition_id)
        if not resolved:
            return ClaimResult(
                success=False,
                user_id=user_id,
                position_id=position_id,
                amount_claimed=0,
                error="Market not yet resolved",
            )

        # Check if this is a winning position
        if position.outcome != resolved["winning_outcome"]:
            return ClaimResult(
                success=False,
                user_id=user_id,
                position_id=position_id,
                amount_claimed=0,
                error="This was not a winning position",
            )

        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return ClaimResult(
                success=False,
                user_id=user_id,
                position_id=position_id,
                amount_claimed=0,
                error="Wallet not found",
            )

        position_dict = {
            "id": position.id,
            "user_id": position.user_id,
            "market_condition_id": position.market_condition_id,
            "token_id": position.token_id,
            "outcome": position.outcome,
            "size": position.size,
            "average_entry_price": position.average_entry_price,
            "market_question": position.market_question,
            "wallet_address": wallet.address,
        }

        result = await self._claim_position(position_dict, resolved["winning_outcome"])

        if result.success:
            # Update claim record
            await self._update_claim_status(position_id, "CLAIMED", result.tx_hash)
        else:
            # Increment retry count
            await self._increment_retry_count(position_id, result.error)

        return result

    async def _get_resolved_market(
        self,
        condition_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get resolved market info."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM resolved_markets
            WHERE condition_id = ?
            """,
            (condition_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _update_claim_status(
        self,
        position_id: int,
        status: str,
        tx_hash: Optional[str] = None,
    ) -> None:
        """Update claim status."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE position_claims
            SET status = ?, tx_hash = ?, claimed_at = ?
            WHERE position_id = ?
            """,
            (status, tx_hash, datetime.utcnow(), position_id),
        )
        await conn.commit()

    async def _increment_retry_count(
        self,
        position_id: int,
        error: str,
    ) -> None:
        """Increment retry count for failed claim."""
        next_retry = datetime.utcnow() + timedelta(hours=RETRY_INTERVAL_HOURS)

        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE position_claims
            SET retry_count = retry_count + 1,
                next_retry_at = ?,
                error_message = ?
            WHERE position_id = ?
            """,
            (next_retry, error, position_id),
        )
        await conn.commit()

    async def get_pending_claims(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending claims for a user (for manual retry UI)."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT pc.*, p.market_question, p.outcome, p.size
            FROM position_claims pc
            JOIN positions p ON pc.position_id = p.id
            WHERE pc.user_id = ? AND pc.status = 'PENDING'
            ORDER BY pc.claimed_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def retry_pending_claims(self) -> List[ClaimResult]:
        """
        Retry all pending claims that are due for retry.

        Called by the retry job (hourly).
        """
        results = []

        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT pc.*, p.market_question, p.outcome, p.size, p.average_entry_price,
                   p.market_condition_id, p.token_id, w.address as wallet_address
            FROM position_claims pc
            JOIN positions p ON pc.position_id = p.id
            JOIN wallets w ON pc.user_id = w.user_id
            WHERE pc.status = 'PENDING'
              AND pc.retry_count < ?
              AND (pc.next_retry_at IS NULL OR pc.next_retry_at <= ?)
            """,
            (MAX_RETRY_COUNT, datetime.utcnow()),
        )
        rows = await cursor.fetchall()

        if not rows:
            return results

        logger.info(f"Retrying {len(rows)} pending claims")

        for row in rows:
            claim = dict(row)
            position = {
                "id": claim["position_id"],
                "user_id": claim["user_id"],
                "market_condition_id": claim["market_condition_id"],
                "token_id": claim["token_id"],
                "outcome": claim["outcome"],
                "size": claim["size"],
                "average_entry_price": claim["average_entry_price"],
                "market_question": claim["market_question"],
                "wallet_address": claim["wallet_address"],
            }

            result = await self._claim_position(position, claim["winning_outcome"])
            results.append(result)

            if result.success:
                await self._update_claim_status(
                    claim["position_id"],
                    "CLAIMED",
                    result.tx_hash,
                )
                await self._notify_user_claim(result, position)
            else:
                await self._increment_retry_count(
                    claim["position_id"],
                    result.error,
                )

                # Mark as failed if max retries exceeded
                if claim["retry_count"] + 1 >= MAX_RETRY_COUNT:
                    await self._update_claim_status(
                        claim["position_id"],
                        "FAILED",
                    )
                    logger.warning(
                        f"Claim for position {claim['position_id']} failed "
                        f"after {MAX_RETRY_COUNT} retries"
                    )

        return results

    async def close(self):
        """Clean up resources."""
        await self.relayer.close()
