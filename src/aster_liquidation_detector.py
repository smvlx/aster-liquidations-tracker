#!/usr/bin/env python3
"""
Aster Liquidation Detection Backend
Monitors liquidations via WebSocket and sends alerts to Telegram.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger

from aster_config import AsterConfig
from aster_symbol_manager import AsterSymbolManager


class AsterLiquidationDetector:
    """Connects to Aster's WebSocket liquidation stream and forwards
    qualifying events (above a USD threshold) to a Telegram channel."""

    def __init__(self):
        self.config = AsterConfig()
        self.bot = Bot(token=self.config.TELEGRAM_BOT_TOKEN)
        self.symbol_manager = AsterSymbolManager()

        self.is_running = False
        self.reconnect_attempts = 0
        self.liquidation_count = 0
        self.last_status_time = time.time()
        self.last_message_time = time.time()
        self.connection_start_time = time.time()

        self._setup_logging()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _setup_logging(self):
        logger.remove()
        logger.add(
            "logs/aster_liquidation_detector.log",
            rotation="1 day",
            retention="7 days",
            level=self.config.LOG_LEVEL,
        )
        logger.add(
            lambda msg: print(msg, end=""),
            level=self.config.LOG_LEVEL,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the liquidation detection service."""
        logger.info("Starting Aster Liquidation Detection Backend")
        logger.info(f"Telegram Channel: {self.config.TELEGRAM_CHANNEL_ID}")
        logger.info(f"WebSocket URL: {self.config.ASTER_WS_URL}")
        logger.info(f"Min liquidation: ${self.config.MIN_LIQUIDATION_USD:,.0f}")

        if not self.config.validate():
            logger.error("Configuration validation failed")
            return

        await self.symbol_manager.load_symbols()
        self.is_running = True

        while self.is_running:
            try:
                await self._connect_and_monitor()
                self.reconnect_attempts = 0
            except Exception as e:
                logger.error(f"Connection error: {e}")
                await self._handle_reconnect()

    async def stop(self):
        """Stop the liquidation detection service."""
        self.is_running = False

    # ------------------------------------------------------------------
    # WebSocket connection
    # ------------------------------------------------------------------

    async def _connect_and_monitor(self):
        """Connect to WebSocket and monitor for liquidations."""
        logger.info(f"Connecting to {self.config.ASTER_WS_URL}")
        self.connection_start_time = time.time()

        async with websockets.connect(
            self.config.ASTER_WS_URL,
            ping_interval=self.config.WEBSOCKET_PING_INTERVAL,
            ping_timeout=self.config.WEBSOCKET_PING_TIMEOUT,
            close_timeout=10,
            open_timeout=20,
            max_size=2**20,
            compression=None,
            max_queue=64,
        ) as ws:
            logger.info("WebSocket connected")
            await self._message_loop(ws)

    async def _message_loop(self, ws):
        """Read messages from the WebSocket until disconnect or lifetime limit."""
        while True:
            connection_age = time.time() - self.connection_start_time

            # Proactive reconnect before server-side 24 h limit
            if connection_age > self.config.MAX_CONNECTION_LIFETIME:
                logger.info(
                    f"Reconnecting after {connection_age:.0f}s (lifetime limit)"
                )
                return

            try:
                message = await asyncio.wait_for(ws.recv(), timeout=60.0)
            except asyncio.TimeoutError:
                await self._handle_idle(ws, connection_age)
                continue

            self.last_message_time = time.time()
            try:
                await self._process_message(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _handle_idle(self, ws, connection_age: float):
        """Handle periods of no incoming messages."""
        # Preemptive reconnect when approaching lifetime limit
        if connection_age > self.config.MAX_CONNECTION_LIFETIME * 0.9:
            logger.info(
                f"Preemptive reconnection at {connection_age:.0f}s "
                "(approaching lifetime limit)"
            )
            raise ConnectionClosed(1000, "Preemptive reconnection")

        silence = time.time() - self.last_message_time
        if silence > 120:
            logger.warning(f"No messages for {silence:.0f}s — sending ping")
            try:
                await ws.send('{"type":"ping"}')
            except Exception as e:
                logger.error(f"Ping failed: {e}")
                raise ConnectionClosed(1011, "Manual ping failed")

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_message(self, message: str):
        """Parse a WebSocket message and dispatch liquidation events."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        if data.get("e") == "forceOrder":
            await self._process_liquidation(data)

    async def _process_liquidation(self, data: Dict[str, Any]):
        """Evaluate a liquidation event and send a Telegram alert if it
        meets the minimum USD threshold."""
        order = data.get("o", {})

        symbol = order.get("s", "Unknown")
        side = order.get("S", "")
        price = float(order.get("ap", order.get("p", "0")))
        quantity = float(order.get("z", order.get("q", "0")))

        usd_amount = price * quantity
        if usd_amount < self.config.MIN_LIQUIDATION_USD:
            return

        self.liquidation_count += 1

        # Format timestamp for logging
        event_time = data.get("E", 0)
        ts = ""
        if event_time:
            ts = f" [{datetime.fromtimestamp(event_time / 1000).strftime('%H:%M:%S')}]"

        logger.warning(
            f"LIQUIDATION #{self.liquidation_count}{ts} | "
            f"{symbol} {side} ${usd_amount:,.0f}"
        )

        await self._send_telegram_alert(symbol, side, price, usd_amount)

        # Periodic status
        now = time.time()
        if now - self.last_status_time >= self.config.STATUS_UPDATE_INTERVAL:
            logger.info(f"Status: {self.liquidation_count} liquidations detected so far")
            self.last_status_time = now

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    async def _send_telegram_alert(
        self, symbol: str, side: str, price: float, usd_amount: float
    ):
        """Format and send a liquidation alert to Telegram."""
        message = self._format_alert(symbol, side, price, usd_amount)
        try:
            await self.bot.send_message(
                chat_id=self.config.TELEGRAM_CHANNEL_ID,
                text=message,
                parse_mode="Markdown",
            )
            logger.info("Alert sent to Telegram")
        except TelegramError as e:
            logger.error(f"Telegram send failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected Telegram error: {e}")

    def _format_alert(
        self, symbol: str, side: str, price: float, usd_amount: float
    ) -> str:
        """Build the Telegram message for a single liquidation event.

        Long liquidations (forced sell) get a red indicator;
        short liquidations (forced buy) get a green one.
        """
        base_symbol = self.symbol_manager.get_base_symbol(symbol)

        if side == "SELL":
            liq_type, emoji = "Long", "\U0001f534"   # red circle
        else:
            liq_type, emoji = "Short", "\U0001f7e2"  # green circle

        usd_str = _format_usd(usd_amount)
        price_str = _format_price(price)

        return f"{emoji} #{base_symbol} {liq_type} Liquidation: {usd_str} @ {price_str}"

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    async def _handle_reconnect(self):
        """Exponential backoff reconnection."""
        self.reconnect_attempts += 1

        if self.reconnect_attempts > self.config.MAX_RECONNECT_ATTEMPTS:
            logger.info("Starting new reconnection cycle with longer delays")
            self.reconnect_attempts = 1

        base = (
            30 if self.reconnect_attempts > self.config.MAX_RECONNECT_ATTEMPTS
            else self.config.RECONNECT_DELAY
        )
        delay = min(base * 2 ** (self.reconnect_attempts - 1), 300)

        logger.warning(
            f"Reconnecting in {delay}s (attempt {self.reconnect_attempts})"
        )
        await asyncio.sleep(delay)
        self.connection_start_time = time.time()


# ======================================================================
# Formatting helpers (module-level, easy to test independently)
# ======================================================================

def _format_usd(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}k"
    return f"${amount:.2f}"


def _format_price(price: float) -> str:
    if price >= 10_000:
        return f"${price:,.0f}"
    if price >= 1_000:
        return f"${price:,.1f}"
    if price >= 100:
        return f"${price:,.2f}"
    if price >= 10:
        return f"${price:,.3f}"
    if price >= 1:
        return f"${price:,.4f}"
    if price >= 0.1:
        return f"${price:.5f}"
    if price >= 0.01:
        return f"${price:.6f}"
    if price > 0:
        return f"${price:.7f}"
    return f"${price:.2f}"
