#!/usr/bin/env python3
"""Quick test script for small $1 trades.

This script helps you test trading with small amounts ($1) using your
deposited funds. It uses the REAL bot implementation - no mocks!

Usage:
    python test_small_trade.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database.connection import Database
from services.trading_service import TradingService
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption
from core.polymarket.gamma_client import GammaClient
from database.repositories.position_repo import PositionRepository
from database.repositories.wallet_repo import WalletRepository
from config.settings import settings


async def test_small_trade():
    """Test a small $1 trade on a real market."""

    print("\n" + "="*80)
    print("SMALL TRADE TEST - $1 Amount")
    print("="*80 + "\n")

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()

    try:
        # Initialize services
        encryption = KeyEncryption(settings.master_encryption_key)
        user_service = UserService(db, encryption)
        trading_service = TradingService(db, encryption)
        wallet_repo = WalletRepository(db)
        position_repo = PositionRepository(db)
        gamma = GammaClient()

        # Get user (assuming you're the first/only user)
        print("📋 Looking up your user account...")

        # You can find your user by telegram_id - replace with your ID
        # Or get the first user for testing
        async with db.get_connection() as conn:
            async with conn.execute("SELECT id FROM users LIMIT 1") as cursor:
                row = await cursor.fetchone()
                if not row:
                    print("❌ No user found! Please register via Telegram bot first.")
                    return
                user_id = row[0]

        print(f"✅ Found user ID: {user_id}")

        # Check wallet balance
        wallet = await wallet_repo.get_by_user_id(user_id)
        if not wallet:
            print("❌ No wallet found!")
            return

        print(f"\n💰 Current Balance:")
        print(f"   Wallet: {wallet.address[:10]}...")
        print(f"   USDC: ${wallet.usdc_balance:.2f}")

        if wallet.usdc_balance < 1.0:
            print("\n❌ Insufficient balance for $1 trade!")
            return

        # Get a market
        print(f"\n🔍 Fetching active markets...")
        markets = await gamma.get_markets(limit=10, offset=0)

        if not markets:
            print("❌ No markets available!")
            return

        # Find a market with good liquidity
        test_market = None
        for market in markets:
            if market.get("active") and market.get("liquidity", 0) > 1000:
                test_market = market
                break

        if not test_market:
            print("❌ No suitable markets found!")
            return

        import json
        clob_token_ids = json.loads(test_market["clobTokenIds"]) if isinstance(test_market["clobTokenIds"], str) else test_market["clobTokenIds"]
        token_id = clob_token_ids[0]  # YES token

        print(f"\n📊 Selected Market:")
        print(f"   Question: {test_market['question']}")
        print(f"   Token ID: {token_id}")
        print(f"   Liquidity: ${test_market.get('liquidity', 0):,.2f}")

        # Confirm trade
        print(f"\n⚠️  About to place REAL trade:")
        print(f"   Amount: $1.00 USDC")
        print(f"   Market: {test_market['question'][:60]}...")
        print(f"   Side: BUY YES")

        response = input("\nProceed with trade? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Trade cancelled.")
            return

        # Place $1 market order
        print(f"\n🔄 Placing $1 market order...")

        result = await trading_service.place_order(
            user_id=user_id,
            market_condition_id=test_market["conditionId"],
            token_id=token_id,
            outcome="YES",
            order_type="MARKET",
            amount=1.0,  # $1 trade!
            market_question=test_market["question"],
        )

        if not result["success"]:
            print(f"\n❌ Trade failed: {result.get('error')}")
            return

        print(f"\n✅ Trade successful!")
        print(f"   Order ID: {result.get('order_id')}")

        # Check updated balance
        updated_wallet = await wallet_repo.get_by_id(wallet.id)
        print(f"\n💰 Updated Balance:")
        print(f"   Previous: ${wallet.usdc_balance:.2f}")
        print(f"   Current: ${updated_wallet.usdc_balance:.2f}")
        print(f"   Spent: ${wallet.usdc_balance - updated_wallet.usdc_balance:.2f}")

        # Check positions
        positions = await position_repo.get_user_positions(user_id)
        if positions:
            print(f"\n📊 Your Positions:")
            for pos in positions:
                print(f"   • {pos.outcome}: {pos.size:.4f} shares @ ${pos.average_entry_price:.4f}")
                if pos.unrealized_pnl:
                    print(f"     P&L: ${pos.unrealized_pnl:+.2f}")

        print(f"\n{'='*80}")
        print(f"✅ TEST COMPLETE!")
        print(f"{'='*80}")
        print(f"\nYou can:")
        print(f"  • Check your position in the bot: /portfolio")
        print(f"  • View on Polymarket: https://polymarket.com")
        print(f"  • Sell your position through the bot")
        print(f"  • Run this script again for another $1 trade\n")

    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_small_trade())
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
