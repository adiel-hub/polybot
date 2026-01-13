"""Test Polymarket web scraper."""

import asyncio
from utils.polymarket_scraper import scrape_market_from_url


async def test_scraper():
    """Test scraping market data from Polymarket."""
    url = "https://polymarket.com/event/israel-strikes-iran-by-january-31-2026"

    print(f"Scraping: {url}\n")

    data = await scrape_market_from_url(url)

    if data:
        print("✅ Successfully scraped market data:")
        print(f"   Condition ID: {data.get('condition_id')}")
        print(f"   Question: {data.get('question', 'N/A')}")
        print(f"   URL: {data.get('url')}")
    else:
        print("❌ Failed to scrape market data")


if __name__ == "__main__":
    asyncio.run(test_scraper())
