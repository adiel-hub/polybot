"""Trade card image generator for sharing closed positions."""

import io
import qrcode
import httpx
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeCardData:
    """Data for generating a trade card image."""

    market_question: str
    outcome: str  # YES or NO or custom outcome name
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percentage: float
    referral_link: str
    market_image_url: Optional[str] = None  # URL to market image


class TradeCardGenerator:
    """Generate shareable trade card images matching the PolyBot design."""

    # Card dimensions (16:9 aspect ratio)
    CARD_WIDTH = 1280
    CARD_HEIGHT = 720

    # Colors
    BG_COLOR = (20, 20, 28)  # Dark background
    PROFIT_COLOR = (0, 255, 136)  # Green for profit
    LOSS_COLOR = (255, 68, 68)  # Red for loss
    TEXT_WHITE = (255, 255, 255)
    TEXT_GRAY = (140, 140, 150)
    DIVIDER_COLOR = (60, 60, 70)

    def __init__(self):
        self.brand_font = None
        self.tagline_font = None
        self.label_font = None
        self.position_font = None
        self.market_font = None
        self.percentage_font = None
        self.footer_font = None
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts for text rendering."""
        # Try multiple font paths for cross-platform compatibility
        font_paths = [
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/Library/Fonts/Arial.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        bold_font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        def load_font(paths, size):
            for path in paths:
                try:
                    return ImageFont.truetype(path, size)
                except (OSError, IOError):
                    continue
            return ImageFont.load_default()

        self.brand_font = load_font(bold_font_paths, 42)
        self.tagline_font = load_font(font_paths, 24)
        self.label_font = load_font(font_paths, 28)
        self.position_font = load_font(bold_font_paths, 36)
        self.market_font = load_font(font_paths, 32)
        self.percentage_font = load_font(bold_font_paths, 120)
        self.footer_font = load_font(font_paths, 26)
        self.footer_small_font = load_font(font_paths, 20)

    def generate(self, data: TradeCardData) -> io.BytesIO:
        """
        Generate a trade card image matching the PolyBot design.

        Args:
            data: Trade card data

        Returns:
            BytesIO buffer containing PNG image
        """
        img = Image.new('RGB', (self.CARD_WIDTH, self.CARD_HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        # === TOP LEFT: PolyBot branding ===
        y_pos = 50

        # Draw PolyBot logo placeholder (simple geometric shape)
        logo_size = 55
        logo_x = 60
        self._draw_polybot_logo(draw, logo_x, y_pos, logo_size)

        # Brand name
        draw.text(
            (logo_x + logo_size + 20, y_pos),
            "PolyBot",
            font=self.brand_font,
            fill=self.TEXT_WHITE
        )

        # Tagline
        draw.text(
            (logo_x + logo_size + 20, y_pos + 45),
            "The fastest way to trade on Polymarket",
            font=self.tagline_font,
            fill=self.TEXT_GRAY
        )

        # === POSITION INFO ===
        y_pos = 170

        # "POSITION:" label
        draw.text(
            (60, y_pos),
            "POSITION:",
            font=self.label_font,
            fill=self.TEXT_GRAY
        )

        # Position/outcome name (bold, white)
        label_bbox = draw.textbbox((0, 0), "POSITION:", font=self.label_font)
        label_width = label_bbox[2] - label_bbox[0]
        draw.text(
            (60 + label_width + 15, y_pos),
            data.outcome.upper(),
            font=self.position_font,
            fill=self.TEXT_WHITE
        )

        # Market question
        y_pos = 220
        draw.text(
            (60, y_pos),
            data.market_question,
            font=self.market_font,
            fill=self.TEXT_GRAY
        )

        # === TOTAL RETURN (Hero element) ===
        y_pos = 320

        # "TOTAL RETURN" label
        draw.text(
            (60, y_pos),
            "TOTAL RETURN",
            font=self.label_font,
            fill=self.TEXT_GRAY
        )

        # Large percentage
        y_pos = 360
        roi_color = self.PROFIT_COLOR if data.pnl_percentage >= 0 else self.LOSS_COLOR
        roi_sign = "+" if data.pnl_percentage >= 0 else ""
        draw.text(
            (60, y_pos),
            f"{roi_sign}{data.pnl_percentage:.2f}%",
            font=self.percentage_font,
            fill=roi_color
        )

        # === RIGHT SIDE: Market image ===
        self._draw_market_image(draw, img, data)

        # === BOTTOM: Footer with QR ===
        self._draw_footer(draw, img, data)

        # Save to buffer
        buffer = io.BytesIO()
        buffer.name = 'trade_card.png'
        img.save(buffer, 'PNG', quality=95)
        buffer.seek(0)

        return buffer

    def _draw_polybot_logo(self, draw: ImageDraw, x: int, y: int, size: int):
        """Draw a simple PolyBot logo (geometric placeholder)."""
        # Draw a simple rounded square with an abstract shape
        rect = [x, y, x + size, y + size]
        draw.rounded_rectangle(rect, radius=12, fill=(40, 40, 50))

        # Draw abstract "send" arrow shape inside
        padding = 12
        center_x = x + size // 2
        center_y = y + size // 2

        # Simple arrow/send icon
        points = [
            (x + padding, y + size - padding),
            (x + padding, y + padding + 8),
            (x + size // 2, y + padding),
            (x + size - padding, y + padding + 8),
            (x + size - padding, y + size - padding),
            (x + size // 2, y + size - padding - 8),
        ]
        draw.polygon(points, fill=self.TEXT_GRAY)

    def _draw_market_image(self, draw: ImageDraw, img: Image, data: TradeCardData):
        """Draw market image area on the right side."""
        # Position for market image (right side)
        img_size = 280
        img_x = self.CARD_WIDTH - img_size - 80
        img_y = 60
        corner_radius = 20

        # Try to load market image from URL
        market_img = None
        if data.market_image_url:
            market_img = self._fetch_image(data.market_image_url)

        if market_img:
            # Resize image to fit the square
            market_img = market_img.convert('RGB')
            market_img = market_img.resize((img_size, img_size), Image.Resampling.LANCZOS)

            # Create rounded corners mask
            mask = Image.new('L', (img_size, img_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle(
                [0, 0, img_size, img_size],
                radius=corner_radius,
                fill=255
            )

            # Apply rounded corners to market image
            rounded_img = Image.new('RGB', (img_size, img_size), self.BG_COLOR)
            rounded_img.paste(market_img, (0, 0), mask)

            # Paste onto main image
            img.paste(rounded_img, (img_x, img_y))
        else:
            # Draw placeholder if no image available
            rect = [img_x, img_y, img_x + img_size, img_y + img_size]
            draw.rounded_rectangle(rect, radius=corner_radius, fill=(30, 60, 120))

            # Draw simple placeholder icon
            center_x = img_x + img_size // 2
            center_y = img_y + img_size // 2
            icon_color = (60, 100, 180)
            draw.rectangle(
                [center_x - 40, center_y - 20, center_x + 40, center_y + 40],
                fill=icon_color
            )

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        """Fetch an image from URL."""
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        except Exception:
            return None

    def _draw_footer(self, draw: ImageDraw, img: Image, data: TradeCardData):
        """Draw the footer section with QR code."""
        y_start = self.CARD_HEIGHT - 130

        # Draw separator line
        draw.line(
            [(40, y_start), (self.CARD_WIDTH - 40, y_start)],
            fill=self.DIVIDER_COLOR,
            width=1
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=1,
        )
        qr.add_data(data.referral_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="white", back_color=self.BG_COLOR)
        qr_img = qr_img.convert('RGB')

        # Resize QR code
        qr_size = 90
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Paste QR code on left side
        qr_x = 60
        qr_y = y_start + 20
        img.paste(qr_img, (qr_x, qr_y))

        # Text next to QR
        text_x = qr_x + qr_size + 25
        text_y = y_start + 35

        draw.text(
            (text_x, text_y),
            "Scan to trade with PolyBot",
            font=self.footer_font,
            fill=self.TEXT_WHITE
        )

        draw.text(
            (text_x, text_y + 35),
            "Telegram native",
            font=self.footer_small_font,
            fill=self.TEXT_GRAY
        )

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."


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
    market_image_url: Optional[str] = None,
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
        referral_link=referral_link,
        market_image_url=market_image_url,
    )
    return generator.generate(data)
