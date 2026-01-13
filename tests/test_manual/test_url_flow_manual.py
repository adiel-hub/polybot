"""Test complete URL to market flow with all fallbacks."""

import asyncio
from services.market_service import MarketService
from utils.url_parser import extract_slug_from_url, extract_url_from_text
from utils.polymarket_scraper import scrape_market_from_url


async def test_complete_flow():
    """Test the complete market URL flow with all fallback mechanisms."""

    url = "https://polymarket.com/event/israel-strikes-iran-by-january-31-2026"

    print("=" * 70)
    print("Testing Complete Market URL Flow")
    print("=" * 70)
    print(f"\nURL: {url}\n")

    # Step 1: Extract slug
    print("Step 1: Extracting slug from URL...")
    slug = extract_slug_from_url(url)
    print(f"✅ Slug extracted: {slug}\n")

    # Step 2: Try API slug lookup
    print("Step 2: Attempting API slug lookup...")
    market_service = MarketService()
    market = await market_service.get_market_by_slug(slug)

    if market:
        print(f"✅ Found via slug: {market.question}")
        await market_service.close()
        return

    print("❌ Slug lookup failed\n")

    # Step 3: Try keyword search
    print("Step 3: Attempting keyword search fallback...")
    search_query = slug.replace("-", " ")
    print(f"Search query: '{search_query}'")

    markets = await market_service.search_markets(search_query, limit=5)

    if markets:
        print(f"✅ Found {len(markets)} results via search:")
        for i, m in enumerate(markets, 1):
            print(f"   {i}. {m.question[:70]}...")
        await market_service.close()
        return

    print("❌ Search failed\n")

    # Step 4: Try web scraping
    print("Step 4: Attempting web scraping fallback...")
    scraped_data = await scrape_market_from_url(url)

    if not scraped_data or not scraped_data.get("condition_id"):
        print("❌ Web scraping failed")
        await market_service.close()
        return

    print(f"✅ Scraped condition_id: {scraped_data['condition_id']}\n")

    # Step 5: Fetch market by condition_id
    print("Step 5: Fetching market details via condition_id...")
    condition_id = scraped_data["condition_id"]
    market = await market_service.get_market_detail(condition_id)

    if market:
        print(f"✅ SUCCESS! Market found:\n")
        print(f"   Question: {market.question}")
        print(f"   Yes Price: {market.yes_price * 100:.1f}c")
        print(f"   No Price: {market.no_price * 100:.1f}c")
        print(f"   Volume 24h: ${market.volume_24h:,.0f}")
        print(f"   Total Volume: ${market.total_volume:,.0f}")
        print(f"   Liquidity: ${market.liquidity:,.0f}")
        print(f"   Condition ID: {market.condition_id}")
    else:
        print("❌ Failed to fetch market by condition_id")

    await market_service.close()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
