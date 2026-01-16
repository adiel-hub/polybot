"""Trade card image generator for sharing closed positions."""

import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeCardData:
    """Data for generating a trade card image."""

    market_question: str
    outcome: str  # YES or NO
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percentage: float
    referral_code: str
    referral_link: str


class TradeCardGenerator:
    """Generate shareable trade card images like Bybit PnL cards."""

    # Card dimensions
    CARD_WIDTH = 800
    CARD_HEIGHT = 1000

    # Colors (Polymarket purple theme)
    BG_COLOR = (18, 18, 28)  # Dark background
    ACCENT_COLOR = (138, 43, 226)  # Purple accent
    PROFIT_COLOR = (0, 255, 136)  # Green for profit
    LOSS_COLOR = (255, 68, 68)  # Red for loss
    TEXT_WHITE = (255, 255, 255)
    TEXT_GRAY = (156, 163, 175)
    CARD_BG = (28, 28, 38)  # Slightly lighter card bg

    def __init__(self):
        # Use default fonts (Pillow will use built-in)
        self.title_font = None
        self.large_font = None
        self.medium_font = None
        self.small_font = None
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts for text rendering."""
        try:
            # Try to load system fonts
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            self.large_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
            self.medium_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except (OSError, IOError):
            # Fallback to default font
            self.title_font = ImageFont.load_default()
            self.large_font = ImageFont.load_default()
            self.medium_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

    def generate(self, data: TradeCardData) -> io.BytesIO:
        """
        Generate a trade card image.

        Args:
            data: Trade card data

        Returns:
            BytesIO buffer containing PNG image
        """
        # Create image
        img = Image.new('RGB', (self.CARD_WIDTH, self.CARD_HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Draw card background
        card_margin = 30
        card_rect = [
            card_margin,
            card_margin,
            self.CARD_WIDTH - card_margin,
            self.CARD_HEIGHT - 180  # Leave room for referral section
        ]
        self._draw_rounded_rect(draw, card_rect, 20, self.CARD_BG)

        # Draw Polymarket logo/text
        y_pos = 60
        draw.text(
            (50, y_pos),
            "POLYMARKET",
            font=self.title_font,
            fill=self.ACCENT_COLOR
        )

        # Draw outcome badge (YES/NO)
        badge_text = f"{data.outcome}"
        badge_color = self.PROFIT_COLOR if data.outcome == "YES" else self.LOSS_COLOR
        self._draw_badge(draw, (620, y_pos - 5), badge_text, badge_color)

        # Draw market question (truncated if too long)
        y_pos = 130
        question = self._truncate_text(data.market_question, 45)
        for line in self._wrap_text(question, 35):
            draw.text((50, y_pos), line, font=self.medium_font, fill=self.TEXT_WHITE)
            y_pos += 35

        # Draw ROI
        y_pos = 250
        draw.text((50, y_pos), "ROI", font=self.medium_font, fill=self.TEXT_GRAY)

        y_pos = 290
        roi_color = self.PROFIT_COLOR if data.pnl_percentage >= 0 else self.LOSS_COLOR
        roi_sign = "+" if data.pnl_percentage >= 0 else ""
        draw.text(
            (50, y_pos),
            f"{roi_sign}{data.pnl_percentage:.2f}%",
            font=self.large_font,
            fill=roi_color
        )

        # Draw PnL amount
        y_pos = 380
        draw.text((50, y_pos), "Profit/Loss", font=self.medium_font, fill=self.TEXT_GRAY)

        y_pos = 420
        pnl_sign = "+" if data.pnl >= 0 else ""
        draw.text(
            (50, y_pos),
            f"{pnl_sign}${data.pnl:.2f}",
            font=self.large_font,
            fill=roi_color
        )

        # Draw entry/exit prices
        y_pos = 520
        draw.text((50, y_pos), "Entry Price", font=self.medium_font, fill=self.TEXT_GRAY)
        y_pos = 555
        draw.text((50, y_pos), f"{data.entry_price:.4f}", font=self.large_font, fill=self.TEXT_WHITE)

        y_pos = 640
        draw.text((50, y_pos), "Exit Price", font=self.medium_font, fill=self.TEXT_GRAY)
        y_pos = 675
        draw.text((50, y_pos), f"{data.exit_price:.4f}", font=self.large_font, fill=self.TEXT_WHITE)

        # Draw decorative element (arrow or rocket-like shape)
        self._draw_profit_indicator(draw, (600, 400), data.pnl_percentage >= 0)

        # Draw referral section at bottom
        self._draw_referral_section(draw, img, data)

        # Save to buffer
        buffer = io.BytesIO()
        buffer.name = 'trade_card.png'
        img.save(buffer, 'PNG', quality=95)
        buffer.seek(0)

        return buffer

    def _draw_rounded_rect(self, draw: ImageDraw, rect: list, radius: int, color: tuple):
        """Draw a rounded rectangle."""
        x1, y1, x2, y2 = rect
        draw.rounded_rectangle(rect, radius=radius, fill=color)

    def _draw_badge(self, draw: ImageDraw, pos: tuple, text: str, color: tuple):
        """Draw a badge with text."""
        x, y = pos
        padding = 15

        # Get text size
        bbox = draw.textbbox((0, 0), text, font=self.medium_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Draw badge background
        badge_rect = [
            x - padding,
            y,
            x + text_width + padding,
            y + text_height + padding * 2
        ]
        draw.rounded_rectangle(badge_rect, radius=8, fill=color)

        # Draw text
        draw.text((x, y + padding // 2), text, font=self.medium_font, fill=self.BG_COLOR)

    def _draw_profit_indicator(self, draw: ImageDraw, pos: tuple, is_profit: bool):
        """Draw a profit/loss indicator (arrows)."""
        x, y = pos
        color = self.PROFIT_COLOR if is_profit else self.LOSS_COLOR

        # Draw multiple arrows
        for i, offset in enumerate([0, 60, 120]):
            arrow_y = y + offset if not is_profit else y + 120 - offset
            alpha = 255 - (i * 60)  # Fade effect

            # Draw upward or downward arrow
            if is_profit:
                points = [
                    (x, arrow_y + 30),
                    (x + 25, arrow_y),
                    (x + 50, arrow_y + 30)
                ]
            else:
                points = [
                    (x, arrow_y),
                    (x + 25, arrow_y + 30),
                    (x + 50, arrow_y)
                ]

            draw.polygon(points, fill=color)

    def _draw_referral_section(self, draw: ImageDraw, img: Image, data: TradeCardData):
        """Draw the referral section at the bottom."""
        y_start = self.CARD_HEIGHT - 160

        # Draw separator line
        draw.line(
            [(30, y_start), (self.CARD_WIDTH - 30, y_start)],
            fill=self.TEXT_GRAY,
            width=1
        )

        # Draw referral text
        y_pos = y_start + 20
        draw.text(
            (50, y_pos),
            "Trade on Polymarket with PolyBot!",
            font=self.medium_font,
            fill=self.TEXT_WHITE
        )

        y_pos += 40
        draw.text(
            (50, y_pos),
            f"Referral Code: {data.referral_code}",
            font=self.title_font,
            fill=self.ACCENT_COLOR
        )

        # Generate and paste QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(data.referral_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="white", back_color=self.BG_COLOR)
        qr_img = qr_img.convert('RGB')

        # Resize QR code
        qr_size = 100
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Paste QR code
        qr_pos = (self.CARD_WIDTH - qr_size - 50, y_start + 30)
        img.paste(qr_img, qr_pos)

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."

    def _wrap_text(self, text: str, max_chars: int) -> list:
        """Wrap text into multiple lines."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines[:3]  # Max 3 lines


# Convenience function
def generate_trade_card(
    market_question: str,
    outcome: str,
    entry_price: float,
    exit_price: float,
    size: float,
    pnl: float,
    pnl_percentage: float,
    referral_code: str,
    referral_link: str,
) -> io.BytesIO:
    """Generate a trade card image."""
    generator = TradeCardGenerator()
    data = TradeCardData(
        market_question=market_question,
        outcome=outcome,
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        pnl=pnl,
        pnl_percentage=pnl_percentage,
        referral_code=referral_code,
        referral_link=referral_link,
    )
    return generator.generate(data)
