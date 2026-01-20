#!/usr/bin/env python3
"""
Reset wallet approval flags to force re-approval on next trade.

Usage:
    python scripts/reset_wallet_approvals.py <wallet_address>
    python scripts/reset_wallet_approvals.py  # Uses default test wallet
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from database.connection import Database
    from config import settings

    # Get wallet address from args or use default
    if len(sys.argv) > 1:
        wallet_address = sys.argv[1]
    else:
        wallet_address = "0x5b56B3871cbcDad6282A5E6f181b3AD5F9758185"

    print(f"\n{'='*60}")
    print(f"Resetting approval flags for wallet: {wallet_address}")
    print(f"{'='*60}\n")

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()

    # Check current state
    conn = await db.get_connection()
    cursor = await conn.execute(
        "SELECT id, user_id, address, safe_deployed, usdc_approved FROM wallets WHERE address = ?",
        (wallet_address,)
    )
    row = await cursor.fetchone()

    if not row:
        print(f"Wallet not found: {wallet_address}")
        await db.close()
        return

    print(f"Current state:")
    print(f"  ID: {row['id']}")
    print(f"  User ID: {row['user_id']}")
    print(f"  Safe Deployed: {bool(row['safe_deployed'])}")
    print(f"  USDC Approved: {bool(row['usdc_approved'])}")
    print()

    # Reset approval flag
    await conn.execute(
        "UPDATE wallets SET usdc_approved = 0 WHERE address = ?",
        (wallet_address,)
    )
    await conn.commit()

    print("Reset usdc_approved to 0")
    print()
    print("On next trade attempt:")
    print("  1. Bot will detect approvals missing")
    print("  2. Bot will set up all 6 approvals via relayer")
    print("  3. Trade will proceed after approvals confirmed")
    print()
    print("Done! Restart the bot and try trading again.")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
