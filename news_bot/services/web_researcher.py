"""Web research service for gathering context about market topics."""

import logging
from dataclasses import dataclass
from typing import List, Optional
import re

import httpx

from core.polymarket.gamma_client import Market

logger = logging.getLogger(__name__)


@dataclass
class ResearchSource:
    """A source from web research."""
    title: str
    url: str
    snippet: str


@dataclass
class ResearchResult:
    """Results from web research about a market topic."""
    query: str
    summary: str
    sources: List[ResearchSource]
    context_snippets: List[str]


class WebResearcherService:
    """
    Searches the web for context about market topics.

    Uses Tavily API which is optimized for AI applications.
    """

    def __init__(self, tavily_api_key: str):
        """
        Initialize the web researcher.

        Args:
            tavily_api_key: Tavily API key for web search
        """
        self.api_key = tavily_api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def research_topic(self, market: Market) -> ResearchResult:
        """
        Research the market topic using web search.

        1. Builds an effective search query from the market question
        2. Performs web search via Tavily API
        3. Returns structured research results with sources

        Args:
            market: Market to research

        Returns:
            ResearchResult with summary and sources
        """
        if not self.api_key:
            logger.warning("No Tavily API key configured, skipping web research")
            return ResearchResult(
                query="",
                summary="",
                sources=[],
                context_snippets=[],
            )

        try:
            # Build search query from market
            search_query = self._build_search_query(market)
            logger.info(f"Researching: {search_query}")

            # Search using Tavily API
            results = await self._search_tavily(search_query)

            # Parse results
            sources = []
            snippets = []

            for result in results.get("results", [])[:5]:
                sources.append(ResearchSource(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", "")[:500],
                ))
                if result.get("content"):
                    snippets.append(result["content"][:300])

            return ResearchResult(
                query=search_query,
                summary=results.get("answer", ""),
                sources=sources,
                context_snippets=snippets,
            )

        except Exception as e:
            logger.error(f"Web research failed: {e}")
            return ResearchResult(
                query=self._build_search_query(market),
                summary="",
                sources=[],
                context_snippets=[],
            )

    async def _search_tavily(self, query: str) -> dict:
        """
        Search using Tavily API.

        Tavily is designed for AI applications and provides
        both search results and AI-generated answers.

        Args:
            query: Search query

        Returns:
            Tavily API response with results and answer
        """
        client = await self._get_client()

        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": False,
                "max_results": 5,
            },
        )
        response.raise_for_status()
        return response.json()

    def _build_search_query(self, market: Market) -> str:
        """
        Build an effective search query from market question.

        Removes betting-specific language and focuses on
        the underlying news event.

        Args:
            market: Market to build query for

        Returns:
            Search query string
        """
        question = market.question

        # Remove common betting phrases
        betting_phrases = [
            r"will\s+",
            r"won't\s+",
            r"does\s+",
            r"doesn't\s+",
            r"is\s+",
            r"isn't\s+",
            r"are\s+",
            r"aren't\s+",
            r"can\s+",
            r"can't\s+",
            r"by\s+\w+\s+\d{1,2},?\s+\d{4}\??",  # "by January 1, 2025?"
            r"\?$",  # Remove trailing question mark
        ]

        query = question
        for phrase in betting_phrases:
            query = re.sub(phrase, " ", query, flags=re.IGNORECASE)

        # Clean up whitespace
        query = " ".join(query.split())

        # Add "news" or "latest" for context
        if market.category:
            query = f"{query} {market.category} news"
        else:
            query = f"{query} latest news"

        return query.strip()
