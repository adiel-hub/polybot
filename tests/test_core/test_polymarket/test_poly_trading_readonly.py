#!/usr/bin/env python3
"""Test Polymarket trading APIs (read-only operations).

Tests everything we can without spending real money:
- Market data fetching
- Order book reading
- Price checking
- Order building (without submitting)
"""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from core.wallet.generator import WalletGenerator
from core.polymarket.gamma_client import GammaMarketClient
import asyncio


def test_clob_client():
    """Test CLOB client operations."""
    print("=" * 60)
    print("POLYMARKET CLOB API TESTS (Read-Only)")
    print("=" * 60)

    # Generate test wallet
    address, private_key = WalletGenerator.create_wallet()
    print(f"\nTest wallet: {address}")

    # Create client
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=private_key,
        signature_type=2,
    )

    # Test 1: Health check
    print("\n1. API Health Check...")
    try:
        ok = client.get_ok()
        print(f"   ✅ Status: {ok}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    # Test 2: Get markets
    print("\n2. Fetching Markets...")
    try:
        markets = client.get_markets()
        print(f"   ✅ Found {len(markets)} markets")
        if markets:
            sample = markets[0]
            print(f"   Sample: {sample.get('question', 'N/A')[:50]}...")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 3: Get a specific market's order book
    print("\n3. Fetching Order Book...")
    try:
        # Get a popular market's token ID
        markets = client.get_markets()
        if markets:
            # Find a market with tokens
            for m in markets[:10]:
                tokens = m.get("tokens", [])
                if tokens:
                    token_id = tokens[0].get("token_id")
                    if token_id:
                        book = client.get_order_book(token_id)
                        print(f"   ✅ Order book fetched")
                        print(f"   Bids: {len(book.bids)} | Asks: {len(book.asks)}")
                        if book.bids:
                            print(f"   Best bid: {book.bids[0].price}")
                        if book.asks:
                            print(f"   Best ask: {book.asks[0].price}")
                        break
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 4: Get API credentials
    print("\n4. Creating API Credentials...")
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print(f"   ✅ Credentials created and set")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    # Test 5: Get open orders (should be empty)
    print("\n5. Checking Open Orders...")
    try:
        orders = client.get_orders()
        print(f"   ✅ Open orders: {len(orders)}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 6: Build an order (WITHOUT submitting)
    print("\n6. Building Order (NOT submitting)...")
    try:
        markets = client.get_markets()
        token_id = None
        for m in markets[:10]:
            tokens = m.get("tokens", [])
            if tokens:
                token_id = tokens[0].get("token_id")
                if token_id:
                    break

        if token_id:
            # Build order args - this creates the order structure
            # but does NOT submit it
            order_args = OrderArgs(
                price=0.50,
                size=1.0,
                side=BUY,
                token_id=token_id,
            )
            print(f"   ✅ Order args created:")
            print(f"      Token: {token_id[:20]}...")
            print(f"      Side: BUY")
            print(f"      Price: $0.50")
            print(f"      Size: 1.0 shares")
            print(f"   ⚠️  Order NOT submitted (would require funds)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    print("\n" + "=" * 60)
    print("CLOB API TESTS COMPLETE")
    print("=" * 60)


async def test_gamma_client():
    """Test Gamma market data API."""
    print("\n" + "=" * 60)
    print("POLYMARKET GAMMA API TESTS (Market Data)")
    print("=" * 60)

    client = GammaMarketClient()

    # Test 1: Get trending markets
    print("\n1. Fetching Trending Markets...")
    try:
        markets = await client.get_trending_markets(limit=5)
        print(f"   ✅ Found {len(markets)} trending markets")
        for i, m in enumerate(markets[:3], 1):
            print(f"   {i}. {m.question[:50]}...")
            print(f"      YES: {m.yes_price:.0%} | NO: {m.no_price:.0%}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 2: Search markets
    print("\n2. Searching Markets...")
    try:
        results = await client.search_markets("bitcoin", limit=3)
        print(f"   ✅ Found {len(results)} results for 'bitcoin'")
        for m in results[:2]:
            print(f"   - {m.question[:50]}...")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 3: Get tags/categories
    print("\n3. Fetching Categories...")
    try:
        tags = await client.get_tags(limit=10)
        print(f"   ✅ Found {len(tags)} categories")
        for t in tags[:5]:
            print(f"   - {t.get('label', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    await client.close()

    print("\n" + "=" * 60)
    print("GAMMA API TESTS COMPLETE")
    print("=" * 60)


def main():
    print("\n🔍 POLYMARKET API COMPREHENSIVE TEST")
    print("Testing all APIs without spending real money\n")

    # Test CLOB (trading) API
    test_clob_client()

    # Test Gamma (market data) API
    asyncio.run(test_gamma_client())

    print("\n" + "=" * 60)
    print("✅ ALL READ-ONLY TESTS COMPLETE")
    print("=" * 60)
    print("\nTo test actual order placement:")
    print("1. Deposit USDC to your wallet")
    print("2. Use the Telegram bot to place a small bet")
    print("=" * 60)


if __name__ == "__main__":
    main()
