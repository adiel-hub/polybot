"""Article generator service using Claude API."""

import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from core.polymarket.gamma_client import Market
from news_bot.services.web_researcher import ResearchResult

logger = logging.getLogger(__name__)


@dataclass
class GeneratedArticle:
    """A generated news article."""
    title: str
    body: str
    tokens_used: int


class ArticleGeneratorService:
    """
    Generates news-style articles using Claude API.

    Creates engaging, informative articles about prediction market topics
    by combining market data with web research context.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2000,
    ):
        """
        Initialize the article generator.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_tokens: Maximum tokens for generated articles
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate_article(
        self,
        market: Market,
        research: ResearchResult,
    ) -> GeneratedArticle:
        """
        Generate a news-style article about the market topic.

        Combines market data with web research to create
        an informative, engaging article.

        Args:
            market: Market to write about
            research: Web research results for context

        Returns:
            GeneratedArticle with title, body, and token usage
        """
        try:
            prompt = self._build_prompt(market, research)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            content = response.content[0].text

            # Extract title and body
            title, body = self._parse_article(content)

            return GeneratedArticle(
                title=title,
                body=body,
                tokens_used=response.usage.output_tokens,
            )

        except Exception as e:
            logger.error(f"Article generation failed: {e}")
            # Return a basic article on failure
            return GeneratedArticle(
                title=f"New Market: {market.question[:50]}...",
                body=self._generate_fallback_article(market),
                tokens_used=0,
            )

    def _build_prompt(self, market: Market, research: ResearchResult) -> str:
        """
        Build the article generation prompt.

        Args:
            market: Market data
            research: Research results

        Returns:
            Formatted prompt for Claude
        """
        # Format sources for prompt
        sources_text = ""
        if research.sources:
            sources_list = [
                f"- {s.title}: {s.url}" for s in research.sources[:3]
            ]
            sources_text = "\n".join(sources_list)

        # Format research context
        context_text = research.summary if research.summary else ""
        if research.context_snippets:
            context_text += "\n\nKey findings:\n"
            context_text += "\n".join(
                f"- {snippet}" for snippet in research.context_snippets[:3]
            )

        return f"""You are a professional news writer for a financial/prediction markets news channel on Telegram.
Write a news article about the following prediction market topic.

**Market Question:** {market.question}

**Market Description:** {market.description or "N/A"}

**Category:** {market.category or "General"}

**Current Odds:**
- YES: {market.yes_price * 100:.1f}%
- NO: {market.no_price * 100:.1f}%

**Trading Activity:**
- 24h Volume: ${market.volume_24h:,.0f}
- Total Volume: ${market.total_volume:,.0f}
- Liquidity: ${market.liquidity:,.0f}

**Research Context:**
{context_text if context_text else "No additional context available."}

**Key Sources:**
{sources_text if sources_text else "No sources available."}

---

Write a compelling news article (300-500 words) that:

1. **HEADLINE**: Start with an engaging headline on its own line (prefix with "HEADLINE: ")
2. **Context**: Provide background about the topic using the research
3. **Newsworthiness**: Explain why this is currently relevant/trending
4. **Market Insight**: Mention the prediction market and what current odds suggest
5. **Balanced**: Remain neutral and informative - present multiple perspectives
6. **NO Financial Advice**: Never recommend betting or give trading advice

**Format for Telegram:**
- Use HTML formatting: <b>bold</b>, <i>italic</i>, <a href="url">links</a>
- Use appropriate emojis for visual appeal (📊 📈 🔮 💰 🗳️ ⚡ etc.)
- Keep paragraphs short (2-3 sentences max)
- Use line breaks between paragraphs for readability
- End with relevant hashtags (2-3 max)

**Important:**
- Write in English
- Be factual and cite research when possible
- Make it engaging but professional
- The article will be posted to a Telegram channel
"""

    def _parse_article(self, content: str) -> tuple[str, str]:
        """
        Parse the generated content to extract title and body.

        Args:
            content: Raw generated content

        Returns:
            Tuple of (title, body)
        """
        lines = content.strip().split("\n")

        # Find headline
        title = ""
        body_start = 0

        for i, line in enumerate(lines):
            if line.startswith("HEADLINE:"):
                title = line.replace("HEADLINE:", "").strip()
                body_start = i + 1
                break
            elif line.startswith("**HEADLINE"):
                # Handle markdown formatted headline
                title = line.replace("**HEADLINE", "").replace("**", "").replace(":", "").strip()
                body_start = i + 1
                break

        # If no headline found, use first line
        if not title and lines:
            title = lines[0].strip()
            body_start = 1

        # Get body (skip empty lines after headline)
        body_lines = lines[body_start:]
        while body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]

        body = "\n".join(body_lines).strip()

        return title, body

    def _generate_fallback_article(self, market: Market) -> str:
        """
        Generate a basic fallback article when AI generation fails.

        Args:
            market: Market data

        Returns:
            Basic article text
        """
        return f"""📊 <b>New Prediction Market</b>

<b>{market.question}</b>

{market.description[:200] + '...' if market.description and len(market.description) > 200 else market.description or 'No description available.'}

<b>Current Market Odds:</b>
• YES: {market.yes_price * 100:.0f}%
• NO: {market.no_price * 100:.0f}%

💰 <b>Trading Activity:</b>
• Total Volume: ${market.total_volume:,.0f}
• Liquidity: ${market.liquidity:,.0f}

#{market.category.lower().replace(' ', '') if market.category else 'predictions'} #polymarket"""
