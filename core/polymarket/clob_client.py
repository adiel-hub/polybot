"""Polymarket CLOB API client wrapper."""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    MarketOrderArgs,
    OrderArgs,
    OrderType,
    BalanceAllowanceParams,
    AssetType,
)
from py_clob_client.order_builder.constants import BUY, SELL
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Result of an order placement."""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    status: Optional[str] = None


class PolymarketCLOB:
    """Wrapper for Polymarket CLOB API operations."""

    def __init__(
        self,
        private_key: str,
        funder_address: Optional[str] = None,
    ):
        """
        Initialize CLOB client.

        Args:
            private_key: Wallet private key for signing
            funder_address: Optional funder address (defaults to wallet address)
        """
        self.private_key = private_key
        self.funder_address = funder_address

        # Configure builder attribution if credentials are provided
        builder_config = None
        if settings.poly_builder_api_key:
            logger.info("Builder credentials found - enabling order attribution")
            builder_creds = BuilderApiKeyCreds(
                key=settings.poly_builder_api_key,
                secret=settings.poly_builder_secret,
                passphrase=settings.poly_builder_passphrase,
            )
            builder_config = BuilderConfig(local_builder_creds=builder_creds)

        # Initialize client
        self.client = ClobClient(
            host=settings.clob_host,
            key=private_key,
            chain_id=settings.chain_id,
            signature_type=0,  # EOA signature
            funder=funder_address,
            builder_config=builder_config,
        )

        self._api_creds: Optional[ApiCreds] = None

    async def initialize(self) -> None:
        """Initialize API credentials."""
        try:
            # Create or derive API credentials
            self._api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(self._api_creds)
            logger.info("CLOB client initialized with API credentials")
        except Exception as e:
            logger.error(f"Failed to initialize CLOB client: {e}")
            raise

    @property
    def api_credentials(self) -> Optional[Dict[str, str]]:
        """Get API credentials for storage."""
        if self._api_creds:
            return {
                "api_key": self._api_creds.api_key,
                "api_secret": self._api_creds.api_secret,
                "api_passphrase": self._api_creds.api_passphrase,
            }
        return None

    def set_api_credentials(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
    ) -> None:
        """Set API credentials from stored values."""
        self._api_creds = ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        )
        self.client.set_api_creds(self._api_creds)

    async def place_market_order(
        self,
        token_id: str,
        amount: float,
        side: str,
    ) -> OrderResult:
        """
        Place a market order using MarketOrderArgs.

        Args:
            token_id: The token ID to trade
            amount: Amount in USDC to spend
            side: "BUY" or "SELL"

        Returns:
            OrderResult with success status and order ID
        """
        try:
            # Use the correct side constant
            side_const = BUY if side.upper() == "BUY" else SELL

            # Create market order using MarketOrderArgs (per documentation)
            order = self.client.create_market_order(
                MarketOrderArgs(
                    token_id=token_id,
                    amount=amount,
                    side=side_const,
                )
            )

            result = self.client.post_order(order, OrderType.FOK)

            if result and "orderID" in result:
                return OrderResult(
                    success=True,
                    order_id=result["orderID"],
                    status="FILLED",
                )
            else:
                return OrderResult(
                    success=False,
                    error=str(result) if result else "Order rejected",
                )

        except Exception as e:
            logger.error(f"Market order failed: {e}")

            # Provide user-friendly error messages
            error_str = str(e)
            if "No orderbook exists" in error_str:
                error_msg = "This market has no active orders. Try a different market or use a limit order."
            elif "not enough balance" in error_str.lower() or "insufficient" in error_str.lower():
                error_msg = "Insufficient balance"
            else:
                error_msg = error_str

            return OrderResult(success=False, error=error_msg)

    async def place_limit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
    ) -> OrderResult:
        """
        Place a limit order (GTC - Good Till Cancelled).

        Args:
            token_id: The token ID to trade
            price: Limit price (0.01 - 0.99)
            size: Number of shares
            side: "BUY" or "SELL"

        Returns:
            OrderResult with success status and order ID
        """
        try:
            # Validate price bounds
            if price < 0.01 or price > 0.99:
                return OrderResult(
                    success=False,
                    error="Price must be between 0.01 and 0.99",
                )

            # Use the correct side constant
            side_const = BUY if side.upper() == "BUY" else SELL

            # Create the order
            order = self.client.create_order(
                OrderArgs(
                    token_id=token_id,
                    price=price,
                    size=size,
                    side=side_const,
                )
            )

            result = self.client.post_order(order, OrderType.GTC)

            if result and "orderID" in result:
                return OrderResult(
                    success=True,
                    order_id=result["orderID"],
                    status="OPEN",
                )
            else:
                return OrderResult(
                    success=False,
                    error=str(result) if result else "Order rejected",
                )

        except Exception as e:
            logger.error(f"Limit order failed: {e}")

            # Provide user-friendly error messages
            error_str = str(e)
            if "not enough balance" in error_str.lower() or "insufficient" in error_str.lower():
                error_msg = "Insufficient balance"
            else:
                error_msg = error_str

            return OrderResult(success=False, error=error_msg)

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: The order ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            result = self.client.cancel(order_id)
            return result is not None
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    async def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.

        Returns:
            Number of orders cancelled
        """
        try:
            result = self.client.cancel_all()
            return len(result) if result else 0
        except Exception as e:
            logger.error(f"Cancel all orders failed: {e}")
            return 0

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.

        Returns:
            List of open orders
        """
        try:
            orders = self.client.get_orders()
            return orders if orders else []
        except Exception as e:
            logger.error(f"Get open orders failed: {e}")
            return []

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details.

        Args:
            order_id: The order ID

        Returns:
            Order details or None
        """
        try:
            return self.client.get_order(order_id)
        except Exception as e:
            logger.error(f"Get order failed: {e}")
            return None

    async def get_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of trades
        """
        try:
            trades = self.client.get_trades()
            return trades[:limit] if trades else []
        except Exception as e:
            logger.error(f"Get trades failed: {e}")
            return []

    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a token.

        Args:
            token_id: The token ID

        Returns:
            Order book with bids and asks
        """
        try:
            book = self.client.get_order_book(token_id)
            return {
                "bids": [{"price": b.price, "size": b.size} for b in book.bids] if book.bids else [],
                "asks": [{"price": a.price, "size": a.size} for a in book.asks] if book.asks else [],
            }
        except Exception as e:
            logger.error(f"Get order book failed: {e}")
            return {"bids": [], "asks": []}

    async def get_best_price(self, token_id: str, side: str) -> Optional[float]:
        """
        Get best available price for a side.

        Args:
            token_id: The token ID
            side: "BUY" or "SELL"

        Returns:
            Best price or None if no orders
        """
        try:
            book = self.client.get_order_book(token_id)

            if side.upper() == "BUY":
                # Best price to buy is lowest ask
                if book.asks:
                    return float(book.asks[0].price)
            else:
                # Best price to sell is highest bid
                if book.bids:
                    return float(book.bids[0].price)

            return None
        except Exception as e:
            logger.error(f"Get best price failed: {e}")
            return None

    async def get_builder_trades(self) -> List[Dict[str, Any]]:
        """
        Get trades attributed to this builder account.

        Returns:
            List of trades credited to your builder
        """
        try:
            if not settings.poly_builder_api_key:
                logger.warning("Builder credentials not configured - cannot fetch builder trades")
                return []

            trades = self.client.get_builder_trades()
            return trades if trades else []
        except Exception as e:
            logger.error(f"Get builder trades failed: {e}")
            return []

    async def check_allowance(self) -> Dict[str, Any]:
        """
        Check current USDC allowance for the CLOB contract.

        Returns:
            Dict with allowance information
        """
        try:
            params = BalanceAllowanceParams(
                asset_type=AssetType.COLLATERAL,
                signature_type=0,
            )
            result = self.client.get_balance_allowance(params)
            return result if result else {}
        except Exception as e:
            logger.error(f"Check allowance failed: {e}")
            return {}

    async def set_allowance(self, amount: Optional[float] = None) -> bool:
        """
        Set USDC allowance for the CLOB contract.

        Args:
            amount: Amount to approve (None for unlimited)

        Returns:
            True if successful
        """
        try:
            # Create allowance params for USDC
            params = BalanceAllowanceParams(
                asset_type=AssetType.COLLATERAL,  # USDC is collateral
                signature_type=0,  # EOA signature
            )

            result = self.client.update_balance_allowance(params)
            logger.info(f"Allowance set successfully: {result}")
            return True
        except Exception as e:
            logger.error(f"Set allowance failed: {e}")
            return False
