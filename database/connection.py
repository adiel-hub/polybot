"""SQLite database connection and initialization."""

import aiosqlite
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None

    async def get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def initialize(self):
        """Create database tables if they don't exist."""
        conn = await self.get_connection()

        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                telegram_username TEXT,
                first_name TEXT,
                last_name TEXT,
                license_accepted INTEGER DEFAULT 0,
                license_accepted_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                settings TEXT DEFAULT '{}',
                totp_secret BLOB,
                totp_secret_salt BLOB,
                totp_verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Wallets table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                address TEXT NOT NULL UNIQUE,
                encrypted_private_key BLOB NOT NULL,
                encryption_salt BLOB NOT NULL,
                usdc_balance REAL DEFAULT 0.0,
                last_balance_check TIMESTAMP,
                api_key_encrypted BLOB,
                api_secret_encrypted BLOB,
                api_passphrase_encrypted BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Orders table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                polymarket_order_id TEXT,
                market_condition_id TEXT NOT NULL,
                market_question TEXT,
                token_id TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                order_type TEXT NOT NULL CHECK(order_type IN ('MARKET', 'LIMIT', 'FOK')),
                price REAL,
                size REAL NOT NULL,
                filled_size REAL DEFAULT 0.0,
                status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED', 'FILLED', 'CANCELLED', 'FAILED')),
                outcome TEXT CHECK(outcome IN ('YES', 'NO')),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Positions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                market_condition_id TEXT NOT NULL,
                market_question TEXT,
                token_id TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('YES', 'NO')),
                size REAL NOT NULL,
                average_entry_price REAL NOT NULL,
                current_price REAL,
                unrealized_pnl REAL,
                realized_pnl REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, token_id)
            )
        """)

        # Stop loss orders table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stop_loss_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                token_id TEXT NOT NULL,
                trigger_price REAL NOT NULL,
                sell_percentage REAL DEFAULT 100.0,
                is_active INTEGER DEFAULT 1,
                triggered_at TIMESTAMP,
                resulting_order_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
                FOREIGN KEY (resulting_order_id) REFERENCES orders(id)
            )
        """)

        # Copy traders table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS copy_traders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trader_address TEXT NOT NULL,
                trader_name TEXT,
                allocation REAL NOT NULL DEFAULT 10.0,
                max_trade_size REAL,
                is_active INTEGER DEFAULT 1,
                total_trades_copied INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0.0,
                last_trade_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, trader_address)
            )
        """)

        # Deposits table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                tx_hash TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                block_number INTEGER NOT NULL,
                status TEXT DEFAULT 'CONFIRMED' CHECK(status IN ('PENDING', 'CONFIRMED', 'FAILED')),
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Withdrawals table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_hash TEXT,
                status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'CONFIRMED', 'FAILED')),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Market cache table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS market_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT UNIQUE NOT NULL,
                question TEXT NOT NULL,
                description TEXT,
                category TEXT,
                tags TEXT,
                image_url TEXT,
                yes_token_id TEXT,
                no_token_id TEXT,
                yes_price REAL,
                no_price REAL,
                volume_24h REAL,
                total_volume REAL,
                liquidity REAL,
                end_date TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Referral commissions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referral_commissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referee_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                tier INTEGER NOT NULL CHECK(tier IN (1, 2, 3)),
                trade_amount REAL NOT NULL,
                trade_fee REAL NOT NULL,
                commission_rate REAL NOT NULL,
                commission_amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(id),
                FOREIGN KEY (referee_id) REFERENCES users(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)

        # Create indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_stop_loss_active ON stop_loss_orders(is_active)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_deposits_tx_hash ON deposits(tx_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_market_cache_active ON market_cache(is_active)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_commissions_referrer ON referral_commissions(referrer_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_commissions_referee ON referral_commissions(referee_id)")

        # Add referral columns to users table if they don't exist
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we check first
        cursor = await conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "referral_code" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        if "referrer_id" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
        if "commission_balance" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN commission_balance REAL DEFAULT 0.0")
        if "total_earned" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN total_earned REAL DEFAULT 0.0")
        if "total_claimed" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN total_claimed REAL DEFAULT 0.0")

        # Add 2FA columns to users table if they don't exist
        if "totp_secret" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN totp_secret BLOB")
        if "totp_secret_salt" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN totp_secret_salt BLOB")
        if "totp_verified_at" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN totp_verified_at TIMESTAMP")

        # Create indexes for referral columns (safe to run even if they exist)
        # Note: UNIQUE constraint is enforced via unique index
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_referrer_id ON users(referrer_id)")

        await conn.commit()
        logger.info("Database tables initialized")
