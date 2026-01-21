"""PostgreSQL database connection and initialization using asyncpg."""

import asyncpg
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL database manager using connection pool."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def get_connection(self) -> asyncpg.Connection:
        """Get a connection from the pool."""
        if self._pool is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return await self._pool.acquire()

    async def release_connection(self, conn: asyncpg.Connection) -> None:
        """Release a connection back to the pool."""
        if self._pool:
            await self._pool.release(conn)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def initialize(self) -> None:
        """Create connection pool and initialize database tables."""
        # Create connection pool
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
        )
        logger.info("Database connection pool created")

        # Create tables
        await self._create_tables()
        logger.info("Database tables initialized")

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        conn = await self.get_connection()
        try:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    telegram_username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    license_accepted INTEGER DEFAULT 0,
                    license_accepted_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    settings TEXT DEFAULT '{}',
                    totp_secret BYTEA,
                    totp_secret_salt BYTEA,
                    totp_verified_at TIMESTAMP,
                    referral_code TEXT,
                    referrer_id INTEGER,
                    commission_balance REAL DEFAULT 0.0,
                    total_earned REAL DEFAULT 0.0,
                    total_claimed REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Wallets table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    address TEXT NOT NULL UNIQUE,
                    eoa_address TEXT,
                    wallet_type TEXT DEFAULT 'EOA' CHECK(wallet_type IN ('EOA', 'SAFE')),
                    safe_deployed INTEGER DEFAULT 0,
                    encrypted_private_key BYTEA NOT NULL,
                    encryption_salt BYTEA NOT NULL,
                    usdc_balance REAL DEFAULT 0.0,
                    last_balance_check TIMESTAMP,
                    api_key_encrypted BYTEA,
                    api_secret_encrypted BYTEA,
                    api_passphrase_encrypted BYTEA,
                    usdc_approved INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Orders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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

            # Price alerts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    market_condition_id TEXT NOT NULL,
                    market_question TEXT,
                    outcome TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('ABOVE', 'BELOW')),
                    is_active INTEGER DEFAULT 1,
                    triggered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    note TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Copy traders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS copy_traders (
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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
                    id SERIAL PRIMARY KEY,
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

            # Operator commissions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS operator_commissions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    order_id INTEGER NOT NULL,
                    trade_type TEXT NOT NULL CHECK(trade_type IN ('BUY', 'SELL')),
                    trade_amount REAL NOT NULL,
                    commission_rate REAL NOT NULL,
                    commission_amount REAL NOT NULL,
                    net_trade_amount REAL NOT NULL,
                    tx_hash TEXT,
                    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'TRANSFERRED', 'FAILED')),
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transferred_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)

            # Posted markets table (for news bot)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS posted_markets (
                    id SERIAL PRIMARY KEY,
                    condition_id TEXT UNIQUE NOT NULL,
                    event_id TEXT,
                    question TEXT NOT NULL,
                    category TEXT,
                    article_title TEXT,
                    telegram_message_id INTEGER,
                    market_created_at TIMESTAMP,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    article_tokens_used INTEGER,
                    research_sources TEXT
                )
            """)

            # Position claims table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS position_claims (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    position_id INTEGER NOT NULL,
                    market_condition_id TEXT NOT NULL,
                    winning_outcome TEXT NOT NULL,
                    amount_claimed REAL NOT NULL,
                    tx_hash TEXT,
                    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'CLAIMED', 'FAILED')),
                    error_message TEXT,
                    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    next_retry_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
                )
            """)

            # Resolved markets cache
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS resolved_markets (
                    id SERIAL PRIMARY KEY,
                    condition_id TEXT UNIQUE NOT NULL,
                    winning_outcome TEXT NOT NULL,
                    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed INTEGER DEFAULT 0
                )
            """)

            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_referrer_id ON users(referrer_id)")
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
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_operator_commissions_user_id ON operator_commissions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_operator_commissions_status ON operator_commissions(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_markets_condition_id ON posted_markets(condition_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_markets_posted_at ON posted_markets(posted_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_position_claims_user_id ON position_claims(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_position_claims_status ON position_claims(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_position_claims_market ON position_claims(market_condition_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_resolved_markets_condition ON resolved_markets(condition_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_resolved_markets_processed ON resolved_markets(processed)")

        finally:
            await self.release_connection(conn)

    async def execute(self, query: str, *args):
        """Execute a query and return the result."""
        conn = await self.get_connection()
        try:
            return await conn.execute(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetch(self, query: str, *args):
        """Execute a query and fetch all rows."""
        conn = await self.get_connection()
        try:
            return await conn.fetch(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetchrow(self, query: str, *args):
        """Execute a query and fetch a single row."""
        conn = await self.get_connection()
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetchval(self, query: str, *args):
        """Execute a query and fetch a single value."""
        conn = await self.get_connection()
        try:
            return await conn.fetchval(query, *args)
        finally:
            await self.release_connection(conn)
