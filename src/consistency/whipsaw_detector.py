"""
Whipsaw Detection Module for Trading Consistency

WHAT IS A WHIPSAW?
A whipsaw in trading refers to a situation where a security's price moves sharply in one 
direction, causing traders to take a position, only to quickly reverse direction, resulting 
in losses. It's like a saw blade cutting back and forth - hence the name "whipsaw".

Example:
- 9:00 AM: Market looks bullish, trader goes long
- 9:30 AM: Market reverses, looks bearish, trader closes long and goes short
- 10:00 AM: Market reverses again to bullish, causing losses on both trades

This module prevents the AI from falling into whipsaw patterns by:
1. Tracking how many times the bias has changed recently
2. Detecting back-and-forth patterns
3. Enforcing stricter rules during volatile/choppy markets

The goal is to prevent overtrading and reduce false signals during unstable market conditions.
"""

import logging
from typing import Dict, List, Optional

from src.config import settings


class WhipsawDetector:
    """
    Detects and prevents whipsaw trading patterns to avoid overtrading.
    
    A whipsaw pattern occurs when the trading bias changes too frequently,
    indicating unclear market conditions that could lead to losses.
    """
    
    def __init__(self):
        """Initialize whipsaw detector."""
        self.logger = logging.getLogger(__name__)
    
    async def check(
        self,
        recent_changes: List[Dict],
        proposed_bias: str,
        current_bias: Optional[str],
        market_condition: str = "normal",
    ) -> Dict:
        """
        Check if the proposed bias change would create a whipsaw pattern.
        
        This method analyzes recent trading bias changes to determine if we're
        changing direction too frequently, which often leads to losses in choppy markets.
        
        Args:
            recent_changes: List of recent bias changes (newest first)
            proposed_bias: The new bias being proposed (bullish/bearish/neutral)
            current_bias: The current active bias
            market_condition: Current market state (normal/volatile/choppy)
            
        Returns:
            Dict containing:
                - passed: Whether the check passed
                - message: Explanation of the result
                - type: "whipsaw" if failed
                - severity: How serious the violation is
                - guidance: What to do instead
        """
        # No history means no whipsaw risk
        if not recent_changes:
            return {"passed": True, "message": "No recent changes - whipsaw not applicable"}
        
        # No actual change means no whipsaw
        if current_bias == proposed_bias:
            return {"passed": True, "message": "Same bias - no change"}
        
        # Filter to only look at bias changes (not other types of changes)
        bias_changes = [
            change for change in recent_changes
            if change.get("type") == "bias_change"
        ]
        
        # Get the maximum allowed changes based on market conditions
        # In volatile/choppy markets, we're MORE strict (allow fewer changes)
        max_changes = self._get_max_changes_threshold(market_condition)
        
        # Check if we've changed bias too many times recently
        if len(bias_changes) >= max_changes:
            self.logger.warning(
                f"Whipsaw detected: {len(bias_changes)} changes in lookback period "
                f"(max allowed: {max_changes})"
            )
            
            return {
                "passed": False,
                "type": "whipsaw",
                "severity": "high",
                "message": f"Too many bias changes ({len(bias_changes)}) in lookback period",
                "current_value": f"{len(bias_changes)} changes",
                "threshold": f"{max_changes} changes per hour",
                "guidance": "Market showing choppy behavior - wait for clearer signal",
                "recent_changes": bias_changes[-3:],  # Show last 3 changes for context
            }
        
        # Check for rapid back-and-forth pattern (A→B→A pattern)
        # This is a classic whipsaw where we flip-flop between two biases
        if len(bias_changes) >= 2:
            # Get the two most recent changes
            last_change = bias_changes[0]  # Most recent
            second_last_change = bias_changes[1]  # Second most recent
            
            # Check if we're going back to where we were 2 changes ago
            # Pattern: We were at A, changed to B, now want to go back to A
            if (last_change["to"] == current_bias and 
                second_last_change["to"] == proposed_bias):
                
                self.logger.warning(
                    f"Back-and-forth pattern detected: "
                    f"{second_last_change['to']} → {last_change['to']} → {proposed_bias}"
                )
                
                return {
                    "passed": False,
                    "type": "whipsaw",
                    "severity": "medium",
                    "message": "Detected back-and-forth bias pattern",
                    "guidance": "Avoid reversing to recently abandoned bias",
                    "pattern": f"{second_last_change['to']} → {last_change['to']} → {proposed_bias}",
                }
        
        # All checks passed
        return {
            "passed": True,
            "message": f"Whipsaw check passed - {len(bias_changes)} recent changes",
        }
    
    def _get_max_changes_threshold(self, market_condition: str) -> int:
        """
        Get maximum allowed bias changes based on market condition.
        
        In volatile or choppy markets, we actually become MORE restrictive
        to avoid getting caught in false breakouts and whipsaws.
        
        Args:
            market_condition: Current market state
            
        Returns:
            Maximum number of allowed bias changes per hour
        """
        if market_condition in ["volatile", "choppy"]:
            # In unstable markets, allow only 1 change per hour
            # This forces the system to be more patient
            return 1
        else:
            # In normal markets, use the configured default
            # (typically 3-4 changes per hour)
            return settings.WHIPSAW_MAX_CHANGES_PER_HOUR