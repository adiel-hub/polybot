#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.

This script reads data from the SQLite database and migrates it to PostgreSQL.
Use this when transitioning from local SQLite to cloud PostgreSQL deployment.

Usage:
    python scripts/migrate_sqlite_to_postgresql.py

Requirements:
    1. Both aiosqlite and asyncpg must be installed
    2. Set DATABASE_URL environment variable for PostgreSQL connection
    3. SQLite database file must exist at ./data/polybot.db

Example:
    export DATABASE_URL="postgresql://user:pass@host:5432/polybot"
    python scripts/migrate_sqlite_to_postgresql.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def migrate():
    """Migrate all data from SQLite to PostgreSQL."""
    import aiosqlite
    import asyncpg
    from config import settings

    # Source: SQLite
    sqlite_path = Path("./data/polybot.db")
    if not sqlite_path.exists():
        print(f"❌ SQLite database not found at: {sqlite_path}")
        print("   Create it first by running the bot with SQLite, or specify correct path")
        return

    # Destination: PostgreSQL
    if not settings.database_url:
        print("❌ DATABASE_URL not set in environment")
        print("   Set it to your PostgreSQL connection string:")
        print("   export DATABASE_URL='postgresql://user:pass@host:5432/polybot'")
        return

    print("\n" + "="*70)
    print("  SQLite → PostgreSQL Migration")
    print("="*70)
    print(f"\n📁 Source: {sqlite_path}")
    print(f"🗄️  Target: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'PostgreSQL'}")
    print()

    # Ask for confirmation
    response = input("⚠️  This will copy all data from SQLite to PostgreSQL. Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return

    print("\n🔄 Starting migration...\n")

    # Connect to SQLite
    sqlite_conn = await aiosqlite.connect(str(sqlite_path))
    sqlite_conn.row_factory = aiosqlite.Row

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(settings.database_url)

    try:
        # Define tables in dependency order (to handle foreign keys)
        tables = [
            "users",
            "wallets",
            "orders",
            "positions",
            "stop_loss_orders",
            "price_alerts",
            "copy_traders",
            "referral_commissions",
            "news_posted_markets",  # news_bot table
        ]

        total_rows = 0

        for table in tables:
            print(f"📦 Migrating {table}...", end=" ", flush=True)

            try:
                # Get data from SQLite
                sqlite_cursor = await sqlite_conn.execute(f"SELECT * FROM {table}")
                rows = await sqlite_cursor.fetchall()

                if not rows:
                    print("(empty)")
                    continue

                # Get column names
                columns = [desc[0] for desc in sqlite_cursor.description]

                # Convert boolean values (SQLite stores as 0/1, PostgreSQL wants TRUE/FALSE)
                boolean_columns = {
                    "users": ["license_accepted", "is_active", "two_factor_enabled"],
                    "wallets": ["safe_deployed", "usdc_approved"],
                    "orders": ["is_active"],
                    "positions": ["is_active"],
                    "stop_loss_orders": ["is_active"],
                    "price_alerts": ["is_active"],
                    "copy_traders": ["is_active"],
                }

                migrated = 0
                for row in rows:
                    values = []
                    for i, col_name in enumerate(columns):
                        value = row[i]

                        # Convert boolean 0/1 to TRUE/FALSE
                        if table in boolean_columns and col_name in boolean_columns[table]:
                            value = bool(value) if value is not None else False

                        values.append(value)

                    # Build parameterized INSERT query
                    placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
                    col_names = ", ".join(columns)
                    query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

                    try:
                        await pg_conn.execute(query, *values)
                        migrated += 1
                    except Exception as e:
                        print(f"\n   ⚠️  Failed to insert row: {e}")
                        print(f"   Data: {dict(zip(columns, values))}")

                print(f"✅ {migrated}/{len(rows)} rows")
                total_rows += migrated

            except Exception as e:
                print(f"❌ Error: {e}")

        print(f"\n{'='*70}")
        print(f"✅ Migration complete! Migrated {total_rows} total rows")
        print("="*70)
        print()
        print("Next steps:")
        print("  1. Verify data in PostgreSQL")
        print("  2. Update your .env to use DATABASE_URL")
        print("  3. Deploy to Render with PostgreSQL database")
        print()

    finally:
        await sqlite_conn.close()
        await pg_conn.close()


async def verify_migration():
    """Verify row counts match between SQLite and PostgreSQL."""
    import aiosqlite
    import asyncpg
    from config import settings

    sqlite_path = Path("./data/polybot.db")
    if not sqlite_path.exists():
        print("SQLite database not found")
        return

    print("\n" + "="*70)
    print("  Migration Verification")
    print("="*70 + "\n")

    sqlite_conn = await aiosqlite.connect(str(sqlite_path))
    pg_conn = await asyncpg.connect(settings.database_url)

    try:
        tables = [
            "users", "wallets", "orders", "positions",
            "stop_loss_orders", "price_alerts", "copy_traders", "referral_commissions"
        ]

        print(f"{'Table':<25} {'SQLite':<15} {'PostgreSQL':<15} {'Status'}")
        print("-" * 70)

        for table in tables:
            try:
                # SQLite count
                sqlite_cursor = await sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
                sqlite_count = (await sqlite_cursor.fetchone())[0]

                # PostgreSQL count
                pg_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")

                status = "✅" if sqlite_count == pg_count else "❌ MISMATCH"
                print(f"{table:<25} {sqlite_count:<15} {pg_count:<15} {status}")
            except Exception as e:
                print(f"{table:<25} {'Error':<15} {str(e):<15} ❌")

        print()

    finally:
        await sqlite_conn.close()
        await pg_conn.close()


async def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        await verify_migration()
    else:
        await migrate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
