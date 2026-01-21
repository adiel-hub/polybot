"""Tests for claim service (simplified EOA version)."""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from database.connection import Database
from services.claim_service import ClaimService, ClaimResult


class TestClaimResult:
    """Tests for ClaimResult dataclass."""

    def test_successful_claim_result(self):
        """Test successful claim result creation."""
        result = ClaimResult(
            success=True,
            user_id=1,
            position_id=10,
            amount_claimed=100.0,
            tx_hash="0xabc123",
        )

        assert result.success is True
        assert result.user_id == 1
        assert result.position_id == 10
        assert result.amount_claimed == 100.0
        assert result.tx_hash == "0xabc123"
        assert result.error is None

    def test_failed_claim_result(self):
        """Test failed claim result creation."""
        result = ClaimResult(
            success=False,
            user_id=1,
            position_id=10,
            amount_claimed=0,
            error="Manual claim required",
        )

        assert result.success is False
        assert result.amount_claimed == 0
        assert result.error == "Manual claim required"


class TestClaimService:
    """Tests for ClaimService (simplified EOA version)."""

    @pytest_asyncio.fixture
    async def claim_service(self, temp_db: Database):
        """Create ClaimService instance for testing."""
        return ClaimService(db=temp_db)

    @pytest.mark.asyncio
    async def test_get_pending_claims_empty(self, claim_service: ClaimService, temp_db: Database):
        """Test get_pending_claims returns empty list (feature disabled in EOA mode)."""
        # Create a test user
        conn = await temp_db.get_connection()
        await conn.execute(
            "INSERT INTO users (telegram_id, telegram_username) VALUES (?, ?)",
            (123456789, "testuser"),
        )
        await conn.commit()

        claims = await claim_service.get_pending_claims(user_id=1)
        assert claims == []

    @pytest.mark.asyncio
    async def test_record_resolved_market(self, claim_service: ClaimService, temp_db: Database):
        """Test recording a resolved market."""
        condition_id = "0x1234567890abcdef"
        winning_outcome = "YES"

        await claim_service._record_resolved_market(condition_id, winning_outcome)

        # Verify record was created
        conn = await temp_db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM resolved_markets WHERE condition_id = ?",
            (condition_id,),
        )
        row = await cursor.fetchone()

        assert row is not None
        assert row["winning_outcome"] == "YES"
        assert row["processed"] == 0

    @pytest.mark.asyncio
    async def test_mark_market_processed(self, claim_service: ClaimService, temp_db: Database):
        """Test marking a market as processed."""
        condition_id = "0x1234567890abcdef"

        # First record the market
        await claim_service._record_resolved_market(condition_id, "NO")

        # Then mark as processed
        await claim_service._mark_market_processed(condition_id)

        # Verify it's marked
        conn = await temp_db.get_connection()
        cursor = await conn.execute(
            "SELECT processed FROM resolved_markets WHERE condition_id = ?",
            (condition_id,),
        )
        row = await cursor.fetchone()

        assert row["processed"] == 1

    @pytest.mark.asyncio
    async def test_close_losing_position(self, claim_service: ClaimService, temp_db: Database):
        """Test closing a losing position."""
        # Create user and position
        conn = await temp_db.get_connection()
        await conn.execute(
            "INSERT INTO users (telegram_id) VALUES (?)",
            (123456789,),
        )
        await conn.execute(
            """INSERT INTO positions
            (user_id, market_condition_id, token_id, outcome, size, average_entry_price, realized_pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, "0xcondition", "token123", "YES", 10.0, 0.50, 0.0),
        )
        await conn.commit()

        position = {
            "id": 1,
            "user_id": 1,
            "size": 10.0,
            "average_entry_price": 0.50,
        }

        await claim_service._close_losing_position(position)

        # Verify position was closed
        cursor = await conn.execute("SELECT size, realized_pnl FROM positions WHERE id = 1")
        row = await cursor.fetchone()

        assert row["size"] == 0
        assert row["realized_pnl"] == -5.0  # -(10 * 0.50)

    @pytest.mark.asyncio
    async def test_manual_claim_not_supported(self, claim_service: ClaimService):
        """Test that manual claim returns error in EOA mode."""
        result = await claim_service.manual_claim(user_id=1, position_id=1)

        assert result.success is False
        assert "polymarket.com" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retry_pending_claims_empty(self, claim_service: ClaimService):
        """Test retry returns empty list (feature disabled in EOA mode)."""
        results = await claim_service.retry_pending_claims()
        assert results == []

    @pytest.mark.asyncio
    async def test_close_does_nothing(self, claim_service: ClaimService):
        """Test close method completes without error."""
        await claim_service.close()  # Should not raise
