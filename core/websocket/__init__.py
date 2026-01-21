"""WebSocket infrastructure for real-time updates.

Note: Deposit detection is now handled by Alchemy webhooks (core/webhook/)
for cost efficiency. The old DepositSubscriber has been removed.
"""

from core.websocket.manager import WebSocketManager
from core.websocket.price_subscriber import PriceSubscriber
from core.websocket.copy_trade_subscriber import CopyTradeSubscriber

__all__ = [
    "WebSocketManager",
    "PriceSubscriber",
    "CopyTradeSubscriber",
]
