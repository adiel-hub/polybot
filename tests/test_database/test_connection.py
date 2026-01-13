"""Tests for database connection module.

Tests the Database class for SQLite connection management
and table initialization.
"""

import os
import tempfile

import pytest
import pytest_asyncio

from database.connection import Database


class TestDatabaseConnection:
    """Test suite for Database class."""

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self):
        """Test that initialize creates all required tables."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()

            # Check all tables exist
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = await cursor.fetchall()
            table_names = [t["name"] for t in tables]

            expected_tables = [
                "users",
                "wallets",
                "orders",
                "positions",
                "stop_loss_orders",
                "copy_traders",
                "deposits",
                "withdrawals",
                "market_cache",
            ]

            for table in expected_tables:
                assert table in table_names, f"Table {table} not found"

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_get_connection_returns_same_connection(self):
        """Test that get_connection returns the same connection instance."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn1 = await db.get_connection()
            conn2 = await db.get_connection()

            assert conn1 is conn2

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_close_clears_connection(self):
        """Test that close properly clears the connection."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            await db.close()

            assert db._connection is None

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self):
        """Test that foreign keys are enabled."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()
            cursor = await conn.execute("PRAGMA foreign_keys")
            result = await cursor.fetchone()

            # foreign_keys should be 1 (enabled)
            assert result[0] == 1

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self):
        """Test that WAL journal mode is enabled."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()
            cursor = await conn.execute("PRAGMA journal_mode")
            result = await cursor.fetchone()

            assert result[0] == "wal"

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_indexes_created(self):
        """Test that indexes are created."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = await cursor.fetchall()
            index_names = [i["name"] for i in indexes]

            expected_indexes = [
                "idx_users_telegram_id",
                "idx_wallets_address",
                "idx_wallets_user_id",
                "idx_orders_user_id",
                "idx_orders_status",
                "idx_positions_user_id",
                "idx_stop_loss_active",
                "idx_deposits_tx_hash",
                "idx_market_cache_active",
            ]

            for index in expected_indexes:
                assert index in index_names, f"Index {index} not found"

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_row_factory_set(self):
        """Test that row_factory is set for dict-like access."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()

            # Insert a test user
            await conn.execute(
                "INSERT INTO users (telegram_id) VALUES (?)",
                (999999999,)
            )
            await conn.commit()

            # Query and check we can access by column name
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (999999999,)
            )
            row = await cursor.fetchone()

            # Should be able to access by column name
            assert row["telegram_id"] == 999999999

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_users_table_constraints(self):
        """Test that users table has proper constraints."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()

            # Insert first user
            await conn.execute(
                "INSERT INTO users (telegram_id) VALUES (?)",
                (111111111,)
            )
            await conn.commit()

            # Try to insert duplicate telegram_id - should fail
            with pytest.raises(Exception):  # IntegrityError
                await conn.execute(
                    "INSERT INTO users (telegram_id) VALUES (?)",
                    (111111111,)
                )
                await conn.commit()

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_orders_table_constraints(self):
        """Test that orders table has proper CHECK constraints."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            db = Database(db_path)
            await db.initialize()

            conn = await db.get_connection()

            # First create a user
            await conn.execute(
                "INSERT INTO users (telegram_id) VALUES (?)",
                (222222222,)
            )
            await conn.commit()

            # Try to insert order with invalid side - should fail
            with pytest.raises(Exception):
                await conn.execute(
                    """INSERT INTO orders
                    (user_id, market_condition_id, token_id, side, order_type, size)
                    VALUES (1, 'cond', 'token', 'INVALID', 'MARKET', 10)"""
                )
                await conn.commit()

            await db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
