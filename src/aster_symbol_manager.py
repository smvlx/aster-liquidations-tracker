import aiohttp
import asyncio
from typing import Dict, Optional
from loguru import logger


class AsterSymbolManager:
    """Manages symbol metadata from Aster exchange."""
    
    def __init__(self):
        self.symbol_map: Dict[str, str] = {}  # symbol -> base_symbol
        self.exchange_info_url = "https://fapi.asterdex.com/fapi/v1/exchangeInfo"
    
    async def load_symbols(self) -> bool:
        """Load symbol metadata from exchangeInfo endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.exchange_info_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        symbols = data.get("symbols", [])
                        
                        for symbol_info in symbols:
                            symbol = symbol_info.get("symbol", "")
                            base_asset = symbol_info.get("baseAsset", "")
                            
                            if symbol and base_asset:
                                self.symbol_map[symbol] = base_asset
                        
                        logger.info(f"✅ Loaded {len(self.symbol_map)} symbols from exchangeInfo")
                        return True
                    else:
                        logger.error(f"❌ Failed to load symbols: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Error loading symbols: {e}")
            return False
    
    def get_base_symbol(self, symbol: str) -> str:
        """Get base symbol from full symbol name."""
        if symbol in self.symbol_map:
            return self.symbol_map[symbol]
        
        # Fallback: remove common quote suffixes
        for suffix in ["USDT", "BUSD", "USDC"]:
            if symbol.endswith(suffix):
                return symbol[:-len(suffix)]
        
        return symbol
