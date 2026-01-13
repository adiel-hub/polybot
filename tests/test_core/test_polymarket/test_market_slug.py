"""Test market slug lookup."""

import asyncio
from core.polymarket.gamma_client import GammaMarketClient
from utils.url_parser import extract_slug_from_url


async def test_slug_lookup():
    """Test fetching market by slug."""
    url = "https://polymarket.com/event/israel-strikes-iran-by-january-31-2026"
    slug = extract_slug_from_url(url)

    print(f"URL: {url}")
    print(f"Extracted slug: {slug}")
    print()

    client = GammaMarketClient()

    # Try slug lookup
    print("Attempting slug lookup...")
    market = await client.get_market_by_slug(slug)

    if market:
        print(f"✅ Found market: {market.question}")
        print(f"   Condition ID: {market.condition_id}")
        print(f"   Yes Price: {market.yes_price}")
        print(f"   No Price: {market.no_price}")
    else:
        print("❌ Market not found via slug")

        # Try searching instead
        print("\nTrying search as fallback...")
        search_query = slug.replace("-", " ")
        results = await client.search_markets(search_query, limit=5)

        if results:
            print(f"Found {len(results)} results:")
            for i, m in enumerate(results, 1):
                print(f"{i}. {m.question[:80]}")
                print(f"   Slug: {getattr(m, 'slug', 'N/A')}")
        else:
            print("No results from search either")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_slug_lookup())