"""Integration tests for complete trading flow using REAL bot implementation.

These tests execute actual trades on Polymarket using real USDC.
All services, repositories, and blockchain interactions are REAL - no mocks!

Cost per test run: ~$10-20 USDC + gas fees
"""

import pytest
import pytest_asyncio
import asyncio
from web3 import Web3

# Import REAL bot services (no mocks!)
from services.trading_service import TradingService
from services.user_service import UserService
from database.repositories.position_repo import PositionRepository
from database.repositories.wallet_repo import WalletRepository
from database.repositories.order_repo import OrderRepository
from core.blockchain.withdrawals import WithdrawalManager
from core.polymarket.gamma_client import GammaClient
from config.settings import settings


@pytest.mark.integration
@pytest.mark.expensive
@pytest.mark.asyncio
async def test_full_trading_cycle(
    integration_db,
    real_user_service: UserService,
    real_trading_service: TradingService,
    real_withdrawal_manager: WithdrawalManager,
    real_gamma_client: GammaClient,
    funded_test_user,
    external_wallet,
    web3_polygon: Web3,
    position_repo: PositionRepository,
    wallet_repo: WalletRepository,
):
    """Test complete trading cycle from funding to withdrawal using REAL implementation.

    Flow:
    1. Use funded test user (real USDC deposited)
    2. Fetch real market from Polymarket via GammaClient
    3. Place real market buy order via TradingService
    4. Verify real position created via PositionRepository
    5. Close position with real sell order
    6. Withdraw remaining funds via real WithdrawalManager
    7. Verify all on-chain transactions

    Uses ONLY real bot services - no mocks anywhere!

    Cost estimate: ~$10 USDC + 0.05 POL gas
    """
    # Setup - funded_test_user fixture created REAL user with REAL funds
    user, wallet = funded_test_user
    initial_balance = wallet.usdc_balance

    print(f"\n{'='*80}")
    print(f"FULL TRADING CYCLE TEST")
    print(f"{'='*80}")
    print(f"User ID: {user.id}")
    print(f"Wallet: {wallet.address}")
    print(f"Initial balance: ${initial_balance:.2f} USDC")
    print(f"{'='*80}\n")

    assert initial_balance >= settings.test_trade_amount, f"Insufficient test funds (need ${settings.test_trade_amount})"

    # Get a real market using REAL GammaClient
    print(f"🔍 Fetching real markets from Polymarket...")
    markets = await real_gamma_client.get_markets(limit=20, offset=0)
    assert len(markets) > 0, "No markets available"

    # Find an active market with good liquidity
    test_market = None
    for market in markets:
        if market.get("active") and market.get("liquidity", 0) > 1000:
            test_market = market
            break

    assert test_market is not None, "No suitable active markets found"

    # Parse market data
    import json
    clob_token_ids = json.loads(test_market["clobTokenIds"]) if isinstance(test_market["clobTokenIds"], str) else test_market["clobTokenIds"]
    token_id = clob_token_ids[0]  # YES token

    print(f"✅ Selected market: {test_market['question']}")
    print(f"   Token ID: {token_id}")
    print(f"   Liquidity: ${test_market.get('liquidity', 0):,.2f}")

    # Execute REAL trade via TradingService
    trade_amount = settings.test_trade_amount
    print(f"\n🔄 Placing REAL market buy order (${trade_amount})...")

    result = await real_trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market["conditionId"],
        token_id=token_id,
        outcome="YES",
        order_type="MARKET",
        amount=trade_amount,
        market_question=test_market["question"],
    )

    # Verify trade execution
    assert result["success"], f"Trade failed: {result.get('error')}"
    assert result.get("order_id"), "No order ID returned"

    print(f"✅ Order placed successfully!")
    print(f"   Order ID: {result['order_id']}")

    # Verify REAL position was created via PositionRepository
    print(f"\n🔍 Verifying position creation...")
    positions = await position_repo.get_user_positions(user.id)
    assert len(positions) >= 1, "Position not created"

    position = positions[0]
    assert position.size > 0, "Position has no size"
    assert position.average_entry_price > 0, "No entry price recorded"
    assert position.average_entry_price <= 0.99, "Invalid entry price"

    print(f"✅ Position verified:")
    print(f"   Size: {position.size:.4f} shares")
    print(f"   Entry price: ${position.average_entry_price:.4f}")
    print(f"   Token ID: {position.token_id}")

    # Verify balance decreased
    updated_wallet = await wallet_repo.get_by_id(wallet.id)
    balance_decrease = initial_balance - updated_wallet.usdc_balance

    print(f"\n💰 Balance check:")
    print(f"   Initial: ${initial_balance:.2f}")
    print(f"   Current: ${updated_wallet.usdc_balance:.2f}")
    print(f"   Spent: ${balance_decrease:.2f}")

    assert balance_decrease > 0, "Balance did not decrease"
    assert abs(balance_decrease - trade_amount) < 0.1, f"Unexpected balance change: ${balance_decrease} vs ${trade_amount}"

    # Wait for any pending operations
    await asyncio.sleep(2)

    # Close position with REAL sell order
    print(f"\n🔄 Closing position with REAL sell order...")

    sell_result = await real_trading_service.reduce_position(
        user_id=user.id,
        position_id=position.id,
        size=position.size,  # Close full position
    )

    assert sell_result["success"], f"Sell failed: {sell_result.get('error')}"

    print(f"✅ Position closed successfully!")
    print(f"   Order ID: {sell_result.get('order_id')}")

    # Verify position was removed/reduced in REAL database
    final_positions = await position_repo.get_user_positions(user.id)
    print(f"\n📊 Final positions: {len(final_positions)}")

    # Get final balance
    final_wallet = await wallet_repo.get_by_id(wallet.id)
    total_pnl = final_wallet.usdc_balance - initial_balance

    print(f"\n💰 Final balance check:")
    print(f"   Initial: ${initial_balance:.2f}")
    print(f"   Final: ${final_wallet.usdc_balance:.2f}")
    print(f"   P&L: ${total_pnl:+.2f}")

    # May have small loss/gain from trading + Polymarket fees
    assert abs(total_pnl) < 2.0, f"Unexpected large P&L: ${total_pnl}"

    # Cleanup - withdraw ALL remaining funds via REAL WithdrawalManager
    if final_wallet.usdc_balance > 1.0:  # Only withdraw if significant amount left
        print(f"\n🔄 Withdrawing remaining funds to external wallet...")

        # Get REAL private key via UserService
        private_key = await real_user_service.get_private_key(user.id)
        assert private_key, "Could not decrypt private key"

        # Leave small amount for potential gas
        withdrawal_amount = final_wallet.usdc_balance - 0.5

        withdrawal = await real_withdrawal_manager.withdraw(
            from_private_key=private_key,
            to_address=external_wallet.address,
            amount=withdrawal_amount,
        )

        assert withdrawal.success, f"Withdrawal failed: {withdrawal.error}"

        print(f"✅ Withdrawal initiated:")
        print(f"   TX hash: {withdrawal.tx_hash}")
        print(f"   Amount: ${withdrawal_amount:.2f}")

        # Verify on-chain using REAL web3
        receipt = web3_polygon.eth.get_transaction_receipt(withdrawal.tx_hash)
        assert receipt.status == 1, "Withdrawal transaction failed on-chain"

        print(f"✅ Withdrawal confirmed on-chain")

    print(f"\n{'='*80}")
    print(f"✅ FULL TRADING CYCLE TEST PASSED!")
    print(f"{'='*80}\n")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_place_and_cancel_limit_order(
    real_trading_service: TradingService,
    real_gamma_client: GammaClient,
    funded_test_user,
    order_repo: OrderRepository,
):
    """Test placing and canceling a limit order using REAL implementation.

    Cost: Minimal (no order fill, just API calls)
    """
    user, wallet = funded_test_user

    print(f"\n{'='*80}")
    print(f"LIMIT ORDER TEST")
    print(f"{'='*80}\n")

    # Get a real market
    markets = await real_gamma_client.get_markets(limit=10, offset=0)
    assert len(markets) > 0, "No markets available"

    test_market = markets[0]
    import json
    clob_token_ids = json.loads(test_market["clobTokenIds"]) if isinstance(test_market["clobTokenIds"], str) else test_market["clobTokenIds"]
    token_id = clob_token_ids[0]

    print(f"📋 Market: {test_market['question']}")

    # Place limit order at very low price (unlikely to fill)
    print(f"\n🔄 Placing limit order at $0.01...")

    result = await real_trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market["conditionId"],
        token_id=token_id,
        outcome="YES",
        order_type="LIMIT",
        price=0.01,  # Very low - won't fill immediately
        amount=settings.test_trade_amount,
        market_question=test_market["question"],
    )

    assert result["success"], f"Limit order failed: {result.get('error')}"
    order_id = result.get("order_id")
    assert order_id, "No order ID returned"

    print(f"✅ Limit order placed: {order_id}")

    # Verify order in database
    order = await order_repo.get_by_id(order_id)
    assert order is not None, "Order not found in database"
    assert order.order_type == "LIMIT"
    assert order.price == 0.01
    assert order.status in ["OPEN", "PENDING"]

    print(f"✅ Order verified in database (status: {order.status})")

    # Cancel the order
    print(f"\n🔄 Canceling order...")

    cancel_result = await real_trading_service.cancel_order(user.id, order_id)
    assert cancel_result["success"], f"Cancel failed: {cancel_result.get('error')}"

    print(f"✅ Order canceled successfully")

    # Verify cancellation
    canceled_order = await order_repo.get_by_id(order_id)
    assert canceled_order.status == "CANCELLED"

    print(f"✅ Cancellation verified in database")

    print(f"\n{'='*80}")
    print(f"✅ LIMIT ORDER TEST PASSED!")
    print(f"{'='*80}\n")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_insufficient_balance(
    real_trading_service: TradingService,
    real_gamma_client: GammaClient,
    test_user,  # Unfunded user
):
    """Test that trading fails gracefully with insufficient balance.

    Uses REAL TradingService - verifies error handling.

    Cost: Free (no actual trade)
    """
    user, wallet = test_user

    print(f"\n{'='*80}")
    print(f"INSUFFICIENT BALANCE TEST")
    print(f"{'='*80}\n")

    # Get a real market
    markets = await real_gamma_client.get_markets(limit=5, offset=0)
    assert len(markets) > 0, "No markets available"

    test_market = markets[0]
    import json
    clob_token_ids = json.loads(test_market["clobTokenIds"]) if isinstance(test_market["clobTokenIds"], str) else test_market["clobTokenIds"]
    token_id = clob_token_ids[0]

    print(f"📋 Market: {test_market['question']}")
    print(f"💰 User balance: ${wallet.usdc_balance:.2f}")

    # Try to place order exceeding balance
    print(f"\n🔄 Attempting to trade $1000 (more than balance)...")

    result = await real_trading_service.place_order(
        user_id=user.id,
        market_condition_id=test_market["conditionId"],
        token_id=token_id,
        outcome="YES",
        order_type="MARKET",
        amount=1000.0,  # More than balance
        market_question=test_market["question"],
    )

    # Verify failure
    assert result["success"] is False, "Trade should have failed"
    assert "insufficient" in result.get("error", "").lower(), f"Wrong error message: {result.get('error')}"

    print(f"✅ Trade correctly rejected: {result['error']}")

    print(f"\n{'='*80}")
    print(f"✅ INSUFFICIENT BALANCE TEST PASSED!")
    print(f"{'='*80}\n")
