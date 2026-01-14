"""Find active markets with order books for testing."""

import asyncio
import httpx
from core.polymarket.gamma_client import GammaMarketClient


async def check_order_book(token_id: str) -> bool:
    """Check if a token has an active order book."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://clob.polymarket.com/book?token_id={token_id}",
                timeout=10.0
            )
            if response.status_code == 200:
                book = response.json()
                return bool(book.get("bids") or book.get("asks"))
            return False
    except Exception:
        return False


async def main():
    print("=" * 80)
    print("FINDING ACTIVE MARKETS WITH LIQUIDITY")
    print("=" * 80)
    print()

    # Get trending markets
    gamma = GammaMarketClient()
    markets = await gamma.get_trending_markets(limit=20)

    print(f"Found {len(markets)} trending markets\n")

    active_markets = []

    for market in markets:
        question = market.question[:60] + "..." if len(market.question) > 60 else market.question

        # Check YES token order book
        has_yes_book = await check_order_book(market.yes_token_id)
        has_no_book = await check_order_book(market.no_token_id)

        if has_yes_book or has_no_book:
            active_markets.append({
                "question": market.question,
                "yes_token": market.yes_token_id,
                "no_token": market.no_token_id,
                "condition_id": market.condition_id,
            })
            print(f"✅ {question}")
            print(f"   YES: {'✓' if has_yes_book else '✗'}  NO: {'✓' if has_no_book else '✗'}")
            print(f"   Condition ID: {market.condition_id}")
            print()
        else:
            print(f"❌ {question} (no order book)")

    print()
    print("=" * 80)
    print(f"SUMMARY: {len(active_markets)}/{len(markets)} markets with active order books")
    print("=" * 80)
    print()

    if active_markets:
        print("✅ These markets are ready for trading:")
        print()
        for i, m in enumerate(active_markets[:5], 1):
            print(f"{i}. {m['question'][:70]}")


if __name__ == "__main__":
    asyncio.run(main())
