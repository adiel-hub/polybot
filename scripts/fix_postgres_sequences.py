#!/usr/bin/env python3
"""
Fix PostgreSQL sequence values after migration from SQLite.

This resets all primary key sequences to match the current max ID values.
Run this after migrating data from SQLite to prevent duplicate key errors.

Usage:
    python scripts/fix_postgres_sequences.py
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def fix_sequences(database_url=None):
    """Fix all PostgreSQL sequences to match current max IDs."""
    import asyncpg

    # Get database URL from parameter, environment, or settings
    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        try:
            from config import settings
            database_url = settings.database_url
        except:
            pass

    if not database_url:
        print("❌ DATABASE_URL not set")
        print("Usage: python scripts/fix_postgres_sequences.py <database_url>")
        print("   or: export DATABASE_URL=<url> && python scripts/fix_postgres_sequences.py")
        return

    print("\n" + "="*70)
    print("  Fix PostgreSQL Sequences")
    print("="*70)
    print(f"\n🗄️  Database: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
    print()

    # Connect to PostgreSQL
    conn = await asyncpg.connect(database_url)

    try:
        # List of tables with SERIAL primary keys
        tables = [
            "users",
            "wallets",
            "orders",
            "positions",
            "stop_loss_orders",
            "price_alerts",
            "copy_traders",
            "referral_commissions",
            "deposits",
            "withdrawals",
            "market_cache",
            "news_posted_markets",
        ]

        for table in tables:
            try:
                # Get the max ID from the table
                max_id = await conn.fetchval(f"SELECT MAX(id) FROM {table}")

                if max_id is None:
                    print(f"⚪ {table:<25} - empty table, skipping")
                    continue

                # Set the sequence to max ID
                sequence_name = f"{table}_id_seq"
                await conn.execute(f"SELECT setval('{sequence_name}', $1)", max_id)

                print(f"✅ {table:<25} - sequence set to {max_id}")

            except Exception as e:
                print(f"⚠️  {table:<25} - {e}")

        print("\n" + "="*70)
        print("✅ Sequences fixed successfully!")
        print("="*70)
        print("\nYou can now create new records without duplicate key errors.\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        # Get database URL from command line argument if provided
        database_url = sys.argv[1] if len(sys.argv) > 1 else None
        asyncio.run(fix_sequences(database_url))
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
