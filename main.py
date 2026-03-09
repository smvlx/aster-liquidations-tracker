#!/usr/bin/env python3
"""Entry point for Aster Liquidation Tracker."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aster_liquidation_detector import AsterLiquidationDetector
from aster_config import AsterConfig


async def main():
    Path("logs").mkdir(exist_ok=True)

    if not AsterConfig.validate():
        sys.exit(1)

    detector = AsterLiquidationDetector()
    await detector.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
