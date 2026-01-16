"""AI Market Analysis Service.

Provides educational market analysis without financial advice.
Uses algorithmic analysis of market data to generate insights.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level indicators."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Sensitivity(str, Enum):
    """Event sensitivity levels."""
    LOW = "Low"
    HIGH = "High"


@dataclass
class MarketAnalysis:
    """Market analysis result."""

    # Market data
    question: str
    yes_price: float
    no_price: float
    volume_24h: float
    total_volume: float
    liquidity: float

    # Analysis metrics
    market_stability: RiskLevel
    event_sensitivity: Sensitivity
    ambiguity_risk: RiskLevel
    crowd_bias: str

    # Insights
    probability_interpretation: str
    risk_factors: list
    price_dynamics: str

    # Educational note
    disclaimer: str


class AIMarketAnalysisService:
    """
    AI-powered market analysis service.

    Provides educational insights about market dynamics without
    giving financial advice or trading recommendations.
    """

    # Keywords that indicate ambiguous market questions
    AMBIGUOUS_KEYWORDS = [
        "before", "official", "confirmed", "announced", "reported",
        "according to", "sources say", "expected", "likely",
        "approximately", "around", "about", "roughly"
    ]

    # Keywords indicating high event sensitivity
    SENSITIVE_KEYWORDS = [
        "election", "vote", "trump", "biden", "president", "political",
        "war", "conflict", "crisis", "emergency", "breaking",
        "court", "ruling", "verdict", "lawsuit", "indictment",
        "fed", "rate", "inflation", "economic", "recession"
    ]

    DISCLAIMER = (
        "⚠️ *Educational Information Only*\n"
        "This analysis explains how the market is pricing this event. "
        "It is NOT financial advice and does NOT recommend any action. "
        "Prediction markets carry significant risk of loss."
    )

    def __init__(self):
        pass

    def analyze_market(
        self,
        question: str,
        yes_price: float,
        no_price: float,
        volume_24h: float = 0,
        total_volume: float = 0,
        liquidity: float = 0,
        price_change_24h: float = 0,
        price_change_7d: float = 0,
    ) -> MarketAnalysis:
        """
        Analyze a market and generate educational insights.

        Args:
            question: The market question
            yes_price: Current YES price (0-1)
            no_price: Current NO price (0-1)
            volume_24h: 24-hour trading volume
            total_volume: Total lifetime volume
            liquidity: Current liquidity
            price_change_24h: Price change in last 24 hours
            price_change_7d: Price change in last 7 days

        Returns:
            MarketAnalysis with insights
        """
        # Calculate analysis metrics
        market_stability = self._calculate_stability(
            price_change_24h, price_change_7d, volume_24h, liquidity
        )

        event_sensitivity = self._calculate_sensitivity(question)
        ambiguity_risk = self._calculate_ambiguity(question)
        crowd_bias = self._calculate_crowd_bias(yes_price, volume_24h, liquidity)

        # Generate insights
        probability_interpretation = self._interpret_probability(
            yes_price, no_price, market_stability
        )

        risk_factors = self._identify_risk_factors(
            question, yes_price, market_stability,
            event_sensitivity, ambiguity_risk
        )

        price_dynamics = self._analyze_price_dynamics(
            price_change_24h, price_change_7d, volume_24h
        )

        return MarketAnalysis(
            question=question,
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=volume_24h,
            total_volume=total_volume,
            liquidity=liquidity,
            market_stability=market_stability,
            event_sensitivity=event_sensitivity,
            ambiguity_risk=ambiguity_risk,
            crowd_bias=crowd_bias,
            probability_interpretation=probability_interpretation,
            risk_factors=risk_factors,
            price_dynamics=price_dynamics,
            disclaimer=self.DISCLAIMER,
        )

    def _calculate_stability(
        self,
        price_change_24h: float,
        price_change_7d: float,
        volume_24h: float,
        liquidity: float,
    ) -> RiskLevel:
        """Calculate market stability level."""
        # High price changes indicate instability
        abs_change_24h = abs(price_change_24h) if price_change_24h else 0
        abs_change_7d = abs(price_change_7d) if price_change_7d else 0

        instability_score = 0

        # Price volatility (24h)
        if abs_change_24h > 0.15:  # >15% change
            instability_score += 3
        elif abs_change_24h > 0.08:  # >8% change
            instability_score += 2
        elif abs_change_24h > 0.03:  # >3% change
            instability_score += 1

        # Price volatility (7d)
        if abs_change_7d > 0.25:  # >25% change
            instability_score += 2
        elif abs_change_7d > 0.12:  # >12% change
            instability_score += 1

        # Low liquidity increases instability
        if liquidity < 10000:
            instability_score += 2
        elif liquidity < 50000:
            instability_score += 1

        # Classify
        if instability_score >= 4:
            return RiskLevel.HIGH
        elif instability_score >= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _calculate_sensitivity(self, question: str) -> Sensitivity:
        """Calculate event sensitivity based on question content."""
        question_lower = question.lower()

        sensitive_count = sum(
            1 for keyword in self.SENSITIVE_KEYWORDS
            if keyword in question_lower
        )

        return Sensitivity.HIGH if sensitive_count >= 1 else Sensitivity.LOW

    def _calculate_ambiguity(self, question: str) -> RiskLevel:
        """Calculate ambiguity risk based on question wording."""
        question_lower = question.lower()

        ambiguous_count = sum(
            1 for keyword in self.AMBIGUOUS_KEYWORDS
            if keyword in question_lower
        )

        # Check for potential interpretation issues
        if "?" not in question:
            ambiguous_count += 1

        if len(question) > 150:  # Long questions may be complex
            ambiguous_count += 1

        if ambiguous_count >= 3:
            return RiskLevel.HIGH
        elif ambiguous_count >= 1:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _calculate_crowd_bias(
        self,
        yes_price: float,
        volume_24h: float,
        liquidity: float,
    ) -> str:
        """Analyze potential crowd bias indicators."""
        # Extreme prices with high volume may indicate FOMO/panic
        if yes_price > 0.85:
            if volume_24h > 100000:
                return "🔴 Strong YES consensus - possible FOMO"
            return "⚠️ Heavy YES lean - limited upside"
        elif yes_price < 0.15:
            if volume_24h > 100000:
                return "🔴 Strong NO consensus - possible panic"
            return "⚠️ Heavy NO lean - limited upside"
        elif 0.45 <= yes_price <= 0.55:
            return "🟢 Balanced - market uncertain"
        elif yes_price > 0.65:
            return "⚠️ YES favored - moderate consensus"
        elif yes_price < 0.35:
            return "⚠️ NO favored - moderate consensus"
        else:
            return "🟡 Slight lean - no strong consensus"

    def _interpret_probability(
        self,
        yes_price: float,
        no_price: float,
        stability: RiskLevel,
    ) -> str:
        """Generate probability interpretation."""
        yes_pct = yes_price * 100

        stability_note = ""
        if stability == RiskLevel.HIGH:
            stability_note = " However, high volatility suggests rapid changes are possible."
        elif stability == RiskLevel.MEDIUM:
            stability_note = " Moderate volatility indicates some uncertainty remains."

        if yes_price > 0.9:
            return (
                f"The market prices this event as highly likely ({yes_pct:.0f}% implied probability). "
                f"This suggests strong consensus, but extreme prices often reflect crowded positioning.{stability_note}"
            )
        elif yes_price > 0.75:
            return (
                f"The market considers this outcome probable ({yes_pct:.0f}% implied). "
                f"While favored, significant uncertainty remains.{stability_note}"
            )
        elif yes_price > 0.55:
            return (
                f"The market slightly favors YES ({yes_pct:.0f}% implied). "
                f"This indicates a lean but not strong conviction.{stability_note}"
            )
        elif yes_price >= 0.45:
            return (
                f"The market is essentially split ({yes_pct:.0f}% YES / {100-yes_pct:.0f}% NO). "
                f"High uncertainty means external events could swing the price significantly.{stability_note}"
            )
        elif yes_price > 0.25:
            return (
                f"The market favors NO ({100-yes_pct:.0f}% implied). "
                f"YES is considered unlikely but not impossible.{stability_note}"
            )
        elif yes_price > 0.1:
            return (
                f"The market strongly favors NO ({100-yes_pct:.0f}% implied). "
                f"YES is seen as a long-shot outcome.{stability_note}"
            )
        else:
            return (
                f"The market prices YES as highly unlikely ({yes_pct:.0f}% implied). "
                f"Extreme low prices often reflect strong consensus or illiquidity.{stability_note}"
            )

    def _identify_risk_factors(
        self,
        question: str,
        yes_price: float,
        stability: RiskLevel,
        sensitivity: Sensitivity,
        ambiguity: RiskLevel,
    ) -> list:
        """Identify risk factors for the market."""
        risks = []

        # Ambiguity risk
        if ambiguity == RiskLevel.HIGH:
            risks.append("🔸 Question wording may have multiple interpretations")
        elif ambiguity == RiskLevel.MEDIUM:
            risks.append("🔸 Some wording ambiguity - check resolution criteria")

        # Sensitivity risk
        if sensitivity == Sensitivity.HIGH:
            risks.append("🔸 High event sensitivity - news can cause rapid swings")

        # Stability risk
        if stability == RiskLevel.HIGH:
            risks.append("🔸 High volatility - prices moving rapidly")
        elif stability == RiskLevel.MEDIUM:
            risks.append("🔸 Moderate volatility - expect price fluctuations")

        # Extreme price risk
        if yes_price > 0.9 or yes_price < 0.1:
            risks.append("🔸 Extreme price - limited room for profit, high loss risk")

        # Crowd behavior
        if yes_price > 0.8 or yes_price < 0.2:
            risks.append("🔸 Strong crowd consensus - contrarian risk exists")

        # Always add general risks
        if not risks:
            risks.append("🔸 Standard market risks apply")

        risks.append("🔸 Resolution depends on specific criteria - read market rules")

        return risks

    def _analyze_price_dynamics(
        self,
        price_change_24h: float,
        price_change_7d: float,
        volume_24h: float,
    ) -> str:
        """Analyze recent price movement dynamics."""
        if not price_change_24h and not price_change_7d:
            return "Limited price history available for analysis."

        abs_24h = abs(price_change_24h) if price_change_24h else 0
        abs_7d = abs(price_change_7d) if price_change_7d else 0

        direction_24h = "up" if price_change_24h > 0 else "down"
        direction_7d = "up" if price_change_7d > 0 else "down"

        if abs_24h > 0.1:  # >10% in 24h
            if volume_24h > 50000:
                return (
                    f"Sharp {abs_24h*100:.1f}% move {direction_24h} in 24h with high volume. "
                    f"This suggests significant new information or a major event. "
                    f"Rapid moves may overshoot and correct."
                )
            else:
                return (
                    f"Sharp {abs_24h*100:.1f}% move {direction_24h} in 24h but lower volume. "
                    f"Could be emotional reaction rather than informed trading. "
                    f"Thin markets can move on small orders."
                )
        elif abs_24h > 0.03:  # 3-10% in 24h
            return (
                f"Moderate {abs_24h*100:.1f}% move {direction_24h} in 24h. "
                f"Market is adjusting to new information or sentiment shifts."
            )
        elif abs_7d > 0.1:  # Calm 24h but volatile week
            return (
                f"Quiet last 24h but {abs_7d*100:.1f}% move {direction_7d} over the week. "
                f"Market may be consolidating after recent movement."
            )
        else:
            return (
                f"Relatively stable price action. "
                f"Market appears to be in a holding pattern awaiting new developments."
            )

    def format_analysis_message(self, analysis: MarketAnalysis) -> str:
        """Format analysis into a Telegram message."""
        # Truncate question if too long
        question_display = analysis.question
        if len(question_display) > 80:
            question_display = question_display[:80] + "..."

        # Format risk factors
        risks_text = "\n".join(analysis.risk_factors)

        message = (
            f"🧠 *AI Market Analysis*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧩 *Question:*\n_{question_display}_\n\n"
            f"📊 *Current Market State:*\n"
            f"├ ✅ Yes: `{analysis.yes_price*100:.1f}%`\n"
            f"├ ❌ No: `{analysis.no_price*100:.1f}%`\n"
            f"├ 📈 Volume (24h): `${analysis.volume_24h:,.0f}`\n"
            f"└ 💧 Liquidity: `${analysis.liquidity:,.0f}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *Market Indicators:*\n"
            f"├ Stability: *{analysis.market_stability.value}*\n"
            f"├ Event Sensitivity: *{analysis.event_sensitivity.value}*\n"
            f"├ Ambiguity Risk: *{analysis.ambiguity_risk.value}*\n"
            f"└ Crowd Bias: {analysis.crowd_bias}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *Probability Interpretation:*\n"
            f"{analysis.probability_interpretation}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *Risk Factors:*\n"
            f"{risks_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 *Price Dynamics:*\n"
            f"{analysis.price_dynamics}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{analysis.disclaimer}"
        )

        return message


# Singleton instance
_ai_analysis_service = None


def get_ai_analysis_service() -> AIMarketAnalysisService:
    """Get or create the AI analysis service instance."""
    global _ai_analysis_service
    if _ai_analysis_service is None:
        _ai_analysis_service = AIMarketAnalysisService()
    return _ai_analysis_service
