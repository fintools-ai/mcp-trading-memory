"""
Get Current Bias Tool

PURPOSE:
This tool retrieves the current trading bias (bullish/bearish/neutral) for a symbol
from the memory store. It's the starting point for all trading decisions.

WHAT IT DOES:
1. Looks up the current bias for a symbol
2. Calculates how long the bias has been held
3. Returns bias details including invalidation levels and confidence

WHY IT'S IMPORTANT:
- Ensures continuity between trading sessions
- Prevents contradictory positions
- Provides context for new decisions
- Shows time held for time gate checks

EXAMPLE USAGE:
Input: {"symbol": "SPY"}
Output: {
    "bias": "bullish",
    "confidence": 80,
    "invalidation_level": 420.50,
    "time_held_minutes": 15,
    "reasoning": "Strong breakout above resistance",
    ...
}
"""

import logging
import re
from typing import Any, Dict

from src.storage.memory_store import MemoryStore


class GetCurrentBiasTool:
    """
    Retrieves the established market bias for a trading symbol.
    
    This tool is the foundation of the memory system - it tells the AI
    what the current trading stance is for any symbol, preventing
    amnesia between different chat sessions.
    """
    
    def __init__(self, memory_store: MemoryStore):
        """
        Initialize the tool with a memory store connection.
        
        Args:
            memory_store: Connection to Redis storage for bias data
        """
        self.memory_store = memory_store
        self.logger = logging.getLogger(__name__)
    
    @property
    def description(self) -> str:
        """Describe what this tool does for the AI."""
        return "Retrieve established market bias and timing context for symbol"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Define the expected input format."""
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol (e.g., SPY, QQQ, AAPL)",
                }
            },
            "required": ["symbol"],
        }
    
    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate that the symbol follows standard format.
        
        Valid symbols are 1-10 uppercase alphanumeric characters.
        Examples: SPY, QQQ, AAPL, MSFT, ES, NQ
        
        Args:
            symbol: Trading symbol to validate
            
        Returns:
            True if valid format, False otherwise
        """
        if not symbol or not isinstance(symbol, str):
            return False
        
        # Standard symbol format: 1-10 uppercase letters/numbers
        # This covers stocks (AAPL), ETFs (SPY), futures (ES), etc.
        return bool(re.match(r"^[A-Z0-9]{1,10}$", symbol.upper()))
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve the current bias for a symbol.
        
        This method:
        1. Validates the input symbol
        2. Queries the memory store for current bias
        3. Adds time held calculation
        4. Returns bias data or indicates no bias exists
        
        Args:
            arguments: Must contain 'symbol' key
            
        Returns:
            Dict containing:
            - If bias exists: Full bias data with time held
            - If no bias: Message suggesting to establish one
            - If error: Error details with fallback guidance
        """
        # Extract and validate symbol
        raw_symbol = arguments.get("symbol", "")
        
        if not raw_symbol:
            return {
                "error": "invalid_input",
                "message": "Symbol is required",
            }
        
        # Normalize symbol to uppercase and strip whitespace
        symbol = raw_symbol.strip().upper()
        
        if not self._validate_symbol(symbol):
            return {
                "error": "invalid_input",
                "message": f"Invalid symbol format: {raw_symbol}. Must be 1-10 alphanumeric characters",
            }
        
        try:
            # Query memory store for current bias
            bias_data = await self.memory_store.get_current_bias(symbol)
            
            if bias_data:
                # Bias exists - return full details
                self.logger.debug(
                    f"Retrieved bias for {symbol}: {bias_data.get('bias')} "
                    f"(held for {bias_data.get('time_held_minutes')} minutes)"
                )
                return bias_data
            else:
                # No bias established yet
                self.logger.debug(f"No bias established for {symbol}")
                return {
                    "bias": None,
                    "message": f"No bias established for {symbol}",
                    "suggestion": "Establish initial bias based on market analysis",
                }
        
        except Exception as e:
            # Storage error - provide fallback guidance
            self.logger.error(f"Failed to retrieve bias for {symbol}: {e}", exc_info=True)
            return {
                "error": "storage_unavailable",
                "message": "Unable to connect to memory storage",
                "fallback": "Continue without memory context - use extra caution",
            }