"""WebSocket connection manager for real-time updates."""

import asyncio
import logging
import json
from typing import Optional, Callable, Dict, Any, Set, Coroutine
from dataclasses import dataclass, field

import websockets

logger = logging.getLogger(__name__)


@dataclass
class ConnectionState:
    """State for a single WebSocket connection."""
    url: str
    websocket: Optional[Any] = None  # WebSocket connection
    is_connected: bool = False
    reconnect_attempts: int = 0
    subscribed_assets: Set[str] = field(default_factory=set)
    last_message_time: float = 0


class WebSocketManager:
    """
    Manages WebSocket connections with auto-reconnect and subscription handling.

    Supports multiple concurrent connections (Polymarket market, user, and Alchemy).
    """

    MAX_RECONNECT_ATTEMPTS = 10
    BASE_RECONNECT_DELAY = 1.0  # seconds
    MAX_RECONNECT_DELAY = 60.0  # seconds
    HEARTBEAT_INTERVAL = 30.0  # seconds

    def __init__(self):
        self._connections: Dict[str, ConnectionState] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the WebSocket manager and all connections."""
        if self._running:
            return

        self._running = True
        logger.info("WebSocket manager starting")

        # Start connection tasks for each registered connection
        for name, state in self._connections.items():
            task = asyncio.create_task(
                self._connection_loop(name),
                name=f"ws_{name}",
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        """Stop the WebSocket manager and close all connections."""
        self._running = False
        logger.info("WebSocket manager stopping")

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close all connections
        for name, state in self._connections.items():
            if state.websocket:
                await state.websocket.close()

        self._tasks.clear()
        logger.info("WebSocket manager stopped")

    def register_connection(
        self,
        name: str,
        url: str,
        message_handler: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Register a new WebSocket connection.

        Args:
            name: Unique identifier for this connection
            url: WebSocket URL to connect to
            message_handler: Async function to handle incoming messages
        """
        self._connections[name] = ConnectionState(url=url)
        self._message_handlers[name] = message_handler
        logger.info(f"Registered WebSocket connection: {name} -> {url}")

    async def subscribe(
        self,
        connection_name: str,
        asset_ids: list[str],
        subscription_message: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Subscribe to assets on a connection.

        Args:
            connection_name: Name of the registered connection
            asset_ids: List of asset/token IDs to subscribe to
            subscription_message: Optional custom subscription message

        Returns:
            True if subscription was sent successfully
        """
        state = self._connections.get(connection_name)
        if not state or not state.websocket:
            logger.warning(f"Cannot subscribe: {connection_name} not connected")
            return False

        state.subscribed_assets.update(asset_ids)

        # Build subscription message
        if subscription_message is None:
            subscription_message = {
                "assets_ids": asset_ids,
                "operation": "subscribe",
            }

        try:
            await state.websocket.send(json.dumps(subscription_message))
            logger.info(f"Subscribed to {len(asset_ids)} assets on {connection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe on {connection_name}: {e}")
            return False

    async def unsubscribe(
        self,
        connection_name: str,
        asset_ids: list[str],
    ) -> bool:
        """Unsubscribe from assets on a connection."""
        state = self._connections.get(connection_name)
        if not state or not state.websocket:
            return False

        state.subscribed_assets -= set(asset_ids)

        message = {
            "assets_ids": asset_ids,
            "operation": "unsubscribe",
        }

        try:
            await state.websocket.send(json.dumps(message))
            logger.info(f"Unsubscribed from {len(asset_ids)} assets on {connection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe on {connection_name}: {e}")
            return False

    def is_connected(self, connection_name: str) -> bool:
        """Check if a connection is active."""
        state = self._connections.get(connection_name)
        return state is not None and state.is_connected

    async def _connection_loop(self, name: str) -> None:
        """Main loop for a single WebSocket connection with auto-reconnect."""
        state = self._connections[name]
        handler = self._message_handlers[name]

        while self._running:
            try:
                await self._connect_and_listen(name, state, handler)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection {name} error: {e}")
                state.is_connected = False

            if not self._running:
                break

            # Exponential backoff for reconnection
            delay = min(
                self.BASE_RECONNECT_DELAY * (2 ** state.reconnect_attempts),
                self.MAX_RECONNECT_DELAY,
            )
            state.reconnect_attempts += 1

            if state.reconnect_attempts > self.MAX_RECONNECT_ATTEMPTS:
                logger.error(f"Max reconnect attempts reached for {name}")
                break

            logger.info(f"Reconnecting {name} in {delay:.1f}s (attempt {state.reconnect_attempts})")
            await asyncio.sleep(delay)

    async def _connect_and_listen(
        self,
        name: str,
        state: ConnectionState,
        handler: Callable,
    ) -> None:
        """Connect to WebSocket and listen for messages."""
        logger.info(f"Connecting to {name}: {state.url}")

        async with websockets.connect(
            state.url,
            ping_interval=self.HEARTBEAT_INTERVAL,
            ping_timeout=10,
        ) as websocket:
            state.websocket = websocket
            state.is_connected = True
            state.reconnect_attempts = 0
            logger.info(f"Connected to {name}")

            # Re-subscribe to previously subscribed assets
            if state.subscribed_assets:
                await self.subscribe(
                    name,
                    list(state.subscribed_assets),
                )

            # Listen for messages
            async for message in websocket:
                state.last_message_time = asyncio.get_event_loop().time()
                try:
                    data = json.loads(message)
                    await handler(name, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {name}: {message[:100]}")
                except Exception as e:
                    logger.error(f"Handler error for {name}: {e}")
