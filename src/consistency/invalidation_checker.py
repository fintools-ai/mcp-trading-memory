"""
Invalidation Level Checker for Trading Consistency

WHAT IS AN INVALIDATION LEVEL?
An invalidation level is a price point that, if breached, proves your trading thesis wrong.
It's a point where you admit the market isn't doing what you expected.

For example:
- Bullish bias with invalidation at $400: If price drops below $400, the bullish thesis is wrong
- Bearish bias with invalidation at $420: If price rises above $420, the bearish thesis is wrong

WHY ARE INVALIDATION LEVELS CRITICAL?
1. Risk Management: Defines your maximum loss before you're wrong
2. Objectivity: Removes emotion - the market decides, not your feelings
3. Capital Preservation: Prevents holding losing positions hoping for reversal
4. Clear Decision Making: Provides concrete exit rules

WHAT DOES THIS MODULE DO?
This module performs two critical checks:

1. INVALIDATION LEVEL CHECK:
   - Prevents changing bias until the invalidation level is actually breached
   - Adds a buffer to prevent whipsaws around the exact level
   - Forces discipline - you can't flip-flop just because you're nervous

2. ADVERSE PRICE MOVEMENT CHECK:
   - Monitors positions that are moving against you
   - Warns when losses exceed certain thresholds (2%, 5%, 10%)
   - Helps prevent small losses from becoming large losses

Example scenario:
- Enter long at $410 with bullish bias, invalidation at $405
- Price drops to $406 - System prevents panic bias change (still above invalidation)
- Price drops to $404 - Invalidation breached, system allows bias change
- Price drops to $400 - Adverse movement check warns of 2.4% loss

This dual protection system ensures you:
1. Give trades room to work (don't exit too early)
2. Exit when truly wrong (don't hold losers)
3. Get warnings as losses mount
"""

import logging
from typing import Dict, List, Optional

from src.config import settings


class InvalidationChecker:
    """
    Monitors invalidation levels and adverse price movements to enforce trading discipline.
    
    This checker ensures that bias changes only occur when market prices definitively
    prove the current thesis wrong, while also warning about mounting losses.
    """
    
    def __init__(self):
        """Initialize invalidation checker."""
        self.logger = logging.getLogger(__name__)
    
    async def check(
        self,
        current_bias_data: Optional[Dict],
        proposed_bias: str,
        current_price: Optional[float] = None,
        memory_store=None,
        symbol: Optional[str] = None,
    ) -> Dict:
        """
        Check if market conditions justify a bias change based on invalidation levels.
        
        This method performs two types of checks:
        1. Invalidation breach check - for bias changes
        2. Adverse movement check - for position monitoring
        
        Args:
            current_bias_data: Current bias info including invalidation level
            proposed_bias: New bias being proposed
            current_price: Current market price (required for checks)
            memory_store: Storage to check position history
            symbol: Trading symbol for position lookup
            
        Returns:
            Dict containing:
                - passed: Whether the check passed
                - type: "invalidation" or "adverse_price_movement" if failed
                - guidance: Specific advice on what to do
        """
        # No existing bias means no invalidation to check
        if not current_bias_data:
            return {"passed": True, "message": "No existing bias - invalidation not applicable"}
        
        current_bias = current_bias_data.get("bias")
        invalidation_level = current_bias_data.get("invalidation_level")
        
        # If maintaining same bias, check for adverse price movements
        if current_bias == proposed_bias:
            # This checks if our position is underwater and getting worse
            if memory_store and symbol and current_price:
                price_check = await self._check_adverse_price_movement(
                    memory_store, symbol, current_bias, current_price
                )
                if not price_check["passed"]:
                    return price_check
            return {"passed": True, "message": "Same bias - price movements acceptable"}
        
        # For bias CHANGES, check if invalidation level was breached
        if not invalidation_level or not current_price:
            self.logger.warning(
                f"Missing data for invalidation check - price: {current_price}, "
                f"invalidation: {invalidation_level}"
            )
            return {
                "passed": True,
                "message": "Missing price/invalidation data - cannot verify",
                "warning": "Proceeding without invalidation check (risky)",
            }
        
        # Add a buffer to the invalidation level to prevent whipsaws
        # Example: If invalidation is $400, we might wait for $398 (0.5% buffer)
        buffer_percent = settings.INVALIDATION_BUFFER_PERCENT
        buffer_amount = invalidation_level * buffer_percent
        
        # Check bullish bias invalidation (price dropping below support)
        if current_bias == "bullish" and proposed_bias in ["bearish", "neutral"]:
            # Bullish invalidation is typically a support level
            # We're bullish above it, but if price breaks below, thesis is wrong
            effective_invalidation = invalidation_level - buffer_amount
            
            if current_price > effective_invalidation:
                # Price hasn't broken below invalidation yet
                self.logger.info(
                    f"Bullish bias still valid - price {current_price} > "
                    f"invalidation {effective_invalidation}"
                )
                
                return {
                    "passed": False,
                    "type": "invalidation",
                    "severity": "medium",
                    "message": f"Price {current_price} still above invalidation {invalidation_level}",
                    "current_value": current_price,
                    "threshold": effective_invalidation,
                    "guidance": (
                        f"Bullish thesis remains valid until price breaks below {effective_invalidation:.2f}. "
                        f"Current price is {current_price - effective_invalidation:.2f} above invalidation. "
                        f"Wait for clear break or provide strong fundamental reason for early exit."
                    ),
                }
        
        # Check bearish bias invalidation (price rising above resistance)
        elif current_bias == "bearish" and proposed_bias in ["bullish", "neutral"]:
            # Bearish invalidation is typically a resistance level
            # We're bearish below it, but if price breaks above, thesis is wrong
            effective_invalidation = invalidation_level + buffer_amount
            
            if current_price < effective_invalidation:
                # Price hasn't broken above invalidation yet
                self.logger.info(
                    f"Bearish bias still valid - price {current_price} < "
                    f"invalidation {effective_invalidation}"
                )
                
                return {
                    "passed": False,
                    "type": "invalidation",
                    "severity": "medium",
                    "message": f"Price {current_price} still below invalidation {invalidation_level}",
                    "current_value": current_price,
                    "threshold": effective_invalidation,
                    "guidance": (
                        f"Bearish thesis remains valid until price breaks above {effective_invalidation:.2f}. "
                        f"Current price is {effective_invalidation - current_price:.2f} below invalidation. "
                        f"Wait for clear break or provide strong fundamental reason for early exit."
                    ),
                }
        
        # Invalidation level has been breached - bias change is justified
        return {
            "passed": True,
            "message": f"Invalidation breached - price {current_price} vs level {invalidation_level}",
        }
    
    async def _check_adverse_price_movement(
        self,
        memory_store,
        symbol: str,
        current_bias: str,
        current_price: float,
    ) -> Dict:
        """
        Monitor existing positions for adverse price movements.
        
        This protects against holding losing positions too long by warning
        when losses exceed certain thresholds (2%, 5%, 10% etc).
        
        Args:
            memory_store: Storage containing position history
            symbol: Trading symbol
            current_bias: Current trading bias
            current_price: Current market price
            
        Returns:
            Check result with warnings if position is underwater
        """
        try:
            # Get recent position entries to find our entry price
            decisions = await memory_store.get_decision_history(
                symbol, limit=10, decision_type="position_entry"
            )
            
            if not decisions:
                return {"passed": True, "message": "No recent position entries to check"}
            
            # Find the most recent entry that matches our current bias
            relevant_entry = None
            for decision in decisions:
                content = decision.get("content", {})
                direction = content.get("direction")
                
                # Match long positions with bullish bias, short with bearish
                if (current_bias == "bullish" and direction == "long") or \
                   (current_bias == "bearish" and direction == "short"):
                    relevant_entry = content
                    break
            
            if not relevant_entry:
                return {"passed": True, "message": "No matching position entry found"}
            
            entry_price = relevant_entry.get("entry_price")
            if not entry_price:
                return {"passed": True, "message": "No entry price recorded"}
            
            # Calculate how much the position is up or down
            if current_bias == "bullish":
                # Long position: profit if price went up, loss if price went down
                price_change_pct = (current_price - entry_price) / entry_price
            else:  # bearish
                # Short position: profit if price went down, loss if price went up
                price_change_pct = (entry_price - current_price) / entry_price
            
            # Check if we've hit any warning thresholds
            violations = []
            for threshold in settings.PRICE_MOVEMENT_THRESHOLDS:
                if price_change_pct <= -threshold["percent"]:
                    violations.append({
                        "percent": threshold["percent"] * 100,
                        "severity": threshold["severity"],
                        "message": threshold["message"],
                    })
            
            if violations:
                # We're in a losing position - warn the user
                most_severe = max(violations, key=lambda x: x["percent"])
                
                self.logger.warning(
                    f"Adverse price movement detected for {symbol}: "
                    f"{abs(price_change_pct)*100:.1f}% loss"
                )
                
                return {
                    "passed": False,
                    "type": "adverse_price_movement",
                    "severity": most_severe["severity"],
                    "message": f"Position down {abs(price_change_pct)*100:.1f}% - {most_severe['message']}",
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "adverse_move_percent": abs(price_change_pct) * 100,
                    "guidance": (
                        f"Position entered at {entry_price:.2f}, now at {current_price:.2f}. "
                        f"Consider: 1) Closing position to limit losses, 2) Changing bias if "
                        f"market conditions have changed, or 3) Hold if conviction remains high "
                        f"and invalidation not breached."
                    ),
                    "violations": violations,
                }
            
            # Position is profitable or within acceptable loss range
            return {
                "passed": True,
                "message": f"Price movement acceptable ({price_change_pct*100:+.1f}%)",
            }
            
        except Exception as e:
            self.logger.error(f"Failed to check adverse price movement: {e}", exc_info=True)
            # Don't block on errors, but log them
            return {
                "passed": True,
                "message": "Could not verify price movements",
                "warning": str(e),
            }