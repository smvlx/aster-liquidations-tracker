import os
import sys

from dotenv import load_dotenv

load_dotenv()


class AsterConfig:
    """Configuration for Aster liquidation detector."""

    # Aster WebSocket settings
    ASTER_WS_URL: str = os.getenv(
        "ASTER_WS_URL", "wss://fstream.asterdex.com/ws/!forceOrder@arr"
    )

    # Telegram settings (required — no defaults)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

    # Liquidation filter settings
    MIN_LIQUIDATION_USD: float = float(os.getenv("MIN_LIQUIDATION_USD", "50000.0"))

    # App settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RECONNECT_DELAY: int = int(os.getenv("RECONNECT_DELAY", "5"))
    MAX_RECONNECT_ATTEMPTS: int = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "10"))
    WEBSOCKET_PING_INTERVAL: int = int(os.getenv("WEBSOCKET_PING_INTERVAL", "20"))
    WEBSOCKET_PING_TIMEOUT: int = int(os.getenv("WEBSOCKET_PING_TIMEOUT", "15"))
    STATUS_UPDATE_INTERVAL: int = int(os.getenv("STATUS_UPDATE_INTERVAL", "300"))
    MAX_CONNECTION_LIFETIME: int = int(os.getenv("MAX_CONNECTION_LIFETIME", "3600"))

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            print("TELEGRAM_BOT_TOKEN is not set. See .env.example for setup instructions.")
            return False

        if not cls.TELEGRAM_CHANNEL_ID:
            print("TELEGRAM_CHANNEL_ID is not set. See .env.example for setup instructions.")
            return False

        return True
