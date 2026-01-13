"""Test market slug lookup with fallback."""

import asyncio
from core.polymarket.gamma_client import GammaMarketClient
from utils.url_parser import extract_slug_from_url


async def test_slug_lookup():
    """Test fetching market by slug with search fallback."""
    url = "https://polymarket.com/event/israel-strikes-iran-by-january-31-2026"
    slug = extract_slug_from_url(url)

    print(f"URL: {url}")
    print(f"Extracted slug: {slug}")
    print()

    client = GammaMarketClient()

    # Try slug lookup
    print("1️⃣ Attempting slug lookup...")
    market = await client.get_market_by_slug(slug)

    if market:
        print(f"✅ Found market: {market.question}")
        print(f"   Condition ID: {market.condition_id}")
        print(f"   Yes Price: {market.yes_price * 100:.1f}c")
        print(f"   No Price: {market.no_price * 100:.1f}c")
    else:
        print("❌ Market not found via slug")

        # Try searching instead
        print("\n2️⃣ Trying search as fallback...")

        # Try different search queries
        queries = [
            slug.replace("-", " "),  # Full slug as words
            "israel iran strikes",    # Key terms
            "israel iran",           # Broader search
        ]

        results = []
        for query in queries:
            print(f"\nTrying query: '{query}'")
            results = await client.search_markets(query, limit=5)
            if results:
                break

        if results:
            print(f"\n✅ Found {len(results)} results:")
            for i, m in enumerate(results, 1):
                print(f"\n{i}. {m.question}")
                print(f"   Yes Price: {m.yes_price * 100:.1f}c")
                print(f"   Volume 24h: ${m.volume_24h:,.0f}")
                print(f"   Condition ID: {m.condition_id[:20]}...")
        else:
            print("❌ No results from search either")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_slug_lookup())
