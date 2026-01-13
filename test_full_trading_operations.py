"""
Comprehensive test of all trading operations using REAL bot services.
Tests: Market orders (YES/NO), Limit orders, Stop loss, Position tracking, P&L calculation
"""
import asyncio
import sys
from decimal import Decimal

from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from database.repositories.order_repo import OrderRepository
from database.repositories.position_repo import PositionRepository
from services.user_service import UserService
from services.trading_service import TradingService
from core.wallet.encryption import KeyEncryption
from core.polymarket.gamma_client import GammaMarketClient
from config.settings import settings


async def main():
    print("=" * 80)
    print("COMPREHENSIVE TRADING OPERATIONS TEST")
    print("=" * 80)
    print(f"Database: {settings.database_path}")
    print(f"Trade amount: ${settings.test_trade_amount}")
    print("=" * 80)
    print()

    # Initialize database and services
    db = Database(settings.database_path)
    await db.initialize()

    key_encryption = KeyEncryption(settings.master_encryption_key)
    user_service = UserService(db, key_encryption)
    trading_service = TradingService(db, key_encryption)
    gamma_client = GammaMarketClient()

    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)
    position_repo = PositionRepository(db)
    order_repo = OrderRepository(db)

    # Get or create test user (using admin user)
    print("📋 Finding existing user...")
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found. Please register via Telegram bot first!")
        await db.close()
        return

    user = users[0]  # Use first user
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"✅ Using user: {user.telegram_id}")
    print(f"💰 Current balance: ${wallet.usdc_balance:.2f}")
    print()

    if wallet.usdc_balance < settings.test_trade_amount * 2:
        print(f"⚠️  Warning: Low balance. Need at least ${settings.test_trade_amount * 2:.2f} for full test")
        print(f"   Current balance: ${wallet.usdc_balance:.2f}")
        print()

    # Get active markets
    print("🔍 Fetching markets from Polymarket...")
    markets = await gamma_client.get_trending_markets(limit=10)

    # Find a good market with liquidity
    test_market = None
    for market in markets:
        if market.is_active and market.liquidity > 5000:
            test_market = market
            break

    if not test_market:
        test_market = markets[0]

    print(f"📊 Selected market: {test_market.question}")
    print(f"   Liquidity: ${test_market.liquidity:,.2f}")
    print(f"   YES price: ${test_market.yes_price:.4f}")
    print(f"   NO price: ${test_market.no_price:.4f}")
    print()

    # ============================================================================
    # TEST 1: MARKET BUY ORDER (YES)
    # ============================================================================
    print("=" * 80)
    print("TEST 1: MARKET BUY ORDER (YES)")
    print("=" * 80)

    trade_amount = settings.test_trade_amount
    print(f"🔄 Placing market BUY order for YES at ${trade_amount}...")

    result = await trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market.condition_id,
        token_id=test_market.yes_token_id,
        outcome="YES",
        order_type="MARKET",
        amount=trade_amount,
        market_question=test_market.question,
    )

    if not result["success"]:
        print(f"❌ Trade failed: {result.get('error', 'Unknown error')}")
        print(f"   Full result: {result}")
        await db.close()
        return

    order_id_yes = result.get("order_id")
    print(f"✅ YES order placed successfully!")
    print(f"   Order ID: {order_id_yes}")

    # Wait for order to process
    await asyncio.sleep(3)

    # Check position
    positions = await position_repo.get_user_positions(user.id)
    yes_position = None
    for pos in positions:
        if pos.token_id == test_market.yes_token_id:
            yes_position = pos
            break

    if yes_position:
        print(f"✅ YES Position created:")
        print(f"   Size: {yes_position.size:.4f} shares")
        print(f"   Entry price: ${yes_position.average_entry_price:.4f}")
        print(f"   Current value: ${yes_position.current_value:.2f}")
        print(f"   P&L: ${yes_position.unrealized_pnl:.2f}")
    else:
        print("⚠️  Position not found (may still be processing)")

    print()

    # ============================================================================
    # TEST 2: MARKET BUY ORDER (NO)
    # ============================================================================
    print("=" * 80)
    print("TEST 2: MARKET BUY ORDER (NO)")
    print("=" * 80)

    print(f"🔄 Placing market BUY order for NO at ${trade_amount}...")

    result = await trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market.condition_id,
        token_id=test_market.no_token_id,
        outcome="NO",
        order_type="MARKET",
        amount=trade_amount,
        market_question=test_market.question,
    )

    if not result["success"]:
        print(f"❌ Trade failed: {result.get('error')}")
    else:
        order_id_no = result.get("order_id")
        print(f"✅ NO order placed successfully!")
        print(f"   Order ID: {order_id_no}")

    await asyncio.sleep(3)

    # Check NO position
    positions = await position_repo.get_user_positions(user.id)
    no_position = None
    for pos in positions:
        if pos.token_id == test_market.no_token_id:
            no_position = pos
            break

    if no_position:
        print(f"✅ NO Position created:")
        print(f"   Size: {no_position.size:.4f} shares")
        print(f"   Entry price: ${no_position.average_entry_price:.4f}")
        print(f"   Current value: ${no_position.current_value:.2f}")
        print(f"   P&L: ${no_position.unrealized_pnl:.2f}")

    print()

    # ============================================================================
    # TEST 3: LIMIT ORDER
    # ============================================================================
    print("=" * 80)
    print("TEST 3: LIMIT ORDER (at low price, won't fill immediately)")
    print("=" * 80)

    limit_price = 0.05  # Low price, won't fill
    print(f"🔄 Placing LIMIT order for YES at ${limit_price:.2f}...")

    result = await trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market.condition_id,
        token_id=test_market.yes_token_id,
        outcome="YES",
        order_type="LIMIT",
        price=limit_price,
        amount=trade_amount,
        market_question=test_market.question,
    )

    if result["success"]:
        limit_order_id = result.get("order_id")
        print(f"✅ Limit order placed!")
        print(f"   Order ID: {limit_order_id}")

        await asyncio.sleep(2)

        # Check order status
        order = await order_repo.get_by_id(limit_order_id)
        if order:
            print(f"   Status: {order.status}")
            print(f"   Price: ${order.price:.4f}")

        # Cancel the limit order
        print(f"\n🔄 Canceling limit order...")
        cancel_result = await trading_service.cancel_order(
            user_id=user.id,
            order_id=limit_order_id
        )

        if cancel_result["success"]:
            print(f"✅ Order canceled successfully")
        else:
            print(f"⚠️  Cancel failed: {cancel_result.get('error')}")
    else:
        print(f"❌ Limit order failed: {result.get('error')}")

    print()

    # ============================================================================
    # TEST 4: STOP LOSS
    # ============================================================================
    print("=" * 80)
    print("TEST 4: STOP LOSS (set on YES position)")
    print("=" * 80)

    if yes_position and yes_position.size > 0:
        stop_loss_price = max(0.01, yes_position.average_entry_price * 0.85)  # 15% below entry
        print(f"🔄 Setting stop loss at ${stop_loss_price:.4f} (entry: ${yes_position.average_entry_price:.4f})...")

        result = await trading_service.set_stop_loss(
            user_id=user.id,
            position_id=yes_position.id,
            stop_loss_price=stop_loss_price
        )

        if result["success"]:
            print(f"✅ Stop loss set successfully!")

            # Verify stop loss
            updated_position = await position_repo.get_by_id(yes_position.id)
            if updated_position and updated_position.stop_loss_price:
                print(f"   Stop loss price: ${updated_position.stop_loss_price:.4f}")
                print(f"   Current price: ${test_market.yes_price:.4f}")
                print(f"   Trigger distance: ${(test_market.yes_price - updated_position.stop_loss_price):.4f}")
        else:
            print(f"❌ Stop loss failed: {result.get('error')}")
    else:
        print("⚠️  No YES position to set stop loss on")

    print()

    # ============================================================================
    # TEST 5: CHECK ALL POSITIONS & P&L
    # ============================================================================
    print("=" * 80)
    print("TEST 5: PORTFOLIO SUMMARY & P&L")
    print("=" * 80)

    positions = await position_repo.get_user_positions(user.id)

    total_value = 0
    total_pnl = 0

    print(f"📊 Active positions: {len(positions)}\n")

    for i, pos in enumerate(positions, 1):
        print(f"Position {i}:")
        print(f"   Token ID: {pos.token_id}")
        print(f"   Size: {pos.size:.4f} shares")
        print(f"   Entry price: ${pos.average_entry_price:.4f}")
        print(f"   Current value: ${pos.current_value:.2f}")
        print(f"   P&L: ${pos.unrealized_pnl:+.2f}")
        if pos.stop_loss_price:
            print(f"   Stop loss: ${pos.stop_loss_price:.4f}")
        print()

        total_value += pos.current_value
        total_pnl += pos.unrealized_pnl

    print(f"💰 Portfolio summary:")
    print(f"   Total value: ${total_value:.2f}")
    print(f"   Total P&L: ${total_pnl:+.2f}")
    print()

    # ============================================================================
    # TEST 6: SELL POSITION (close YES position)
    # ============================================================================
    print("=" * 80)
    print("TEST 6: SELL POSITION (close YES position)")
    print("=" * 80)

    if yes_position and yes_position.size > 0:
        print(f"🔄 Selling YES position ({yes_position.size:.4f} shares)...")

        result = await trading_service.close_position(
            user_id=user.id,
            position_id=yes_position.id,
            percentage=100  # Close entire position
        )

        if result["success"]:
            print(f"✅ Position closed successfully!")
            print(f"   Final P&L: ${result.get('pnl', 0):+.2f}")

            # Check if position is closed
            await asyncio.sleep(2)
            updated_position = await position_repo.get_by_id(yes_position.id)
            if updated_position:
                print(f"   Remaining size: {updated_position.size:.4f}")
            else:
                print(f"   Position fully closed and removed")
        else:
            print(f"❌ Close failed: {result.get('error')}")
    else:
        print("⚠️  No YES position to close")

    print()

    # ============================================================================
    # TEST 7: PARTIAL SELL (50% of NO position)
    # ============================================================================
    print("=" * 80)
    print("TEST 7: PARTIAL SELL (50% of NO position)")
    print("=" * 80)

    if no_position and no_position.size > 0:
        original_size = no_position.size
        print(f"🔄 Selling 50% of NO position ({original_size * 0.5:.4f} shares)...")

        result = await trading_service.close_position(
            user_id=user.id,
            position_id=no_position.id,
            percentage=50  # Close half
        )

        if result["success"]:
            print(f"✅ Partial close successful!")
            print(f"   P&L on sold shares: ${result.get('pnl', 0):+.2f}")

            # Check remaining size
            await asyncio.sleep(2)
            updated_position = await position_repo.get_by_id(no_position.id)
            if updated_position:
                print(f"   Original size: {original_size:.4f}")
                print(f"   Remaining size: {updated_position.size:.4f}")
        else:
            print(f"❌ Partial close failed: {result.get('error')}")
    else:
        print("⚠️  No NO position for partial close")

    print()

    # ============================================================================
    # FINAL SUMMARY
    # ============================================================================
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    # Get updated wallet balance
    updated_wallet = await wallet_repo.get_by_user_id(user.id)
    balance_change = updated_wallet.usdc_balance - wallet.usdc_balance

    print(f"💰 Wallet balance:")
    print(f"   Starting: ${wallet.usdc_balance:.2f}")
    print(f"   Current: ${updated_wallet.usdc_balance:.2f}")
    print(f"   Change: ${balance_change:+.2f}")
    print()

    # Get all orders
    orders = await order_repo.get_user_orders(user.id)
    print(f"📋 Total orders placed: {len(orders)}")

    filled = sum(1 for o in orders if o.status == "FILLED")
    open_orders = sum(1 for o in orders if o.status in ["OPEN", "PENDING"])
    canceled = sum(1 for o in orders if o.status == "CANCELED")

    print(f"   Filled: {filled}")
    print(f"   Open: {open_orders}")
    print(f"   Canceled: {canceled}")
    print()

    # Final positions
    final_positions = await position_repo.get_user_positions(user.id)
    print(f"📊 Active positions: {len(final_positions)}")

    for pos in final_positions:
        print(f"   {pos.token_id[:8]}... | {pos.size:.4f} shares | P&L: ${pos.unrealized_pnl:+.2f}")

    print()
    print("=" * 80)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 80)

    await db.close()
    await gamma_client.close()


if __name__ == "__main__":
    asyncio.run(main())
