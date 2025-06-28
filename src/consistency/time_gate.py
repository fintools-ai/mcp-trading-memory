"""
Time Gate Module for 0DTE Trading Consistency

WHAT IS A TIME GATE?
A time gate is a minimum holding period for a trading bias before allowing changes.
This is especially critical for 0DTE (Zero Days to Expiration) options trading.

WHAT IS 0DTE TRADING?
0DTE refers to options contracts that expire on the same day they are traded. These are
extremely time-sensitive instruments where:
- Options lose value rapidly throughout the day (theta decay)
- Small price movements can cause large percentage gains/losses
- Timing is absolutely critical - being wrong for even 5-10 minutes can be costly

WHY DO WE NEED A TIME GATE?
In 0DTE trading, frequent bias changes are particularly dangerous because:
1. Each trade has high transaction costs (bid-ask spreads are wider)
2. Options premiums decay rapidly - you lose money just by waiting
3. Quick reversals often mean buying high and selling low
4. The market needs time to "prove" a direction is real

Example scenario without time gate:
- 9:35 AM: See bullish signal, buy calls for $1.00
- 9:37 AM: Small pullback, get scared, sell calls for $0.80 (loss: $0.20)
- 9:40 AM: Market resumes up, missed the move

With 3-minute time gate:
- 9:35 AM: See bullish signal, buy calls for $1.00
- 9:37 AM: Small pullback happens, but time gate prevents exit
- 9:40 AM: Market continues up, calls now worth $1.50 (profit: $0.50)

The time gate forces patience and prevents emotional/reactive trading.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.config import settings


class TimeGate:
    """
    Enforces minimum holding periods for trading biases in 0DTE trading.
    
    This prevents rapid bias changes that often lead to losses in fast-moving
    options markets where timing and patience are critical.
    """
    
    def __init__(self):
        """Initialize time gate."""
        self.logger = logging.getLogger(__name__)
    
    async def check(
        self,
        current_bias_data: Optional[Dict],
        proposed_bias: str,
        market_condition: str = "normal",
        override_time_gate: bool = False,
    ) -> Dict:
        """
        Check if enough time has passed since the last bias change.
        
        For 0DTE trading, we enforce a strict minimum holding period (typically 3 minutes)
        before allowing any bias change. This prevents overtrading and ensures each
        position has time to work.
        
        Args:
            current_bias_data: Current bias info including time held
            proposed_bias: New bias being proposed (bullish/bearish/neutral)
            market_condition: Market state (ignored for 0DTE - time gate always applies)
            override_time_gate: Emergency override flag (use with extreme caution)
            
        Returns:
            Dict containing:
                - passed: Whether the time gate check passed
                - message: Explanation
                - type: "time_gate" if failed
                - time_remaining: How much longer to wait
                - guidance: What to do
        """
        # DANGEROUS: Override should only be used in emergency situations
        # like system errors or critical market events
        if override_time_gate:
            self.logger.warning(
                "TIME GATE OVERRIDE - This is dangerous for 0DTE trading! "
                "Should only be used in emergencies."
            )
            return {"passed": True, "message": "Time gate overridden (WARNING: risky for 0DTE)"}
        
        # No existing bias means this is the first bias - no time restriction
        if not current_bias_data:
            return {"passed": True, "message": "No existing bias - time gate not applicable"}
        
        # If we're not actually changing bias, no need to check time
        current_bias = current_bias_data.get("bias")
        if current_bias == proposed_bias:
            return {"passed": True, "message": "Same bias - no change needed"}
        
        # Get how long we've held the current bias
        time_held_minutes = current_bias_data.get("time_held_minutes", 0)
        
        # For 0DTE trading, we use a strict time gate (typically 3 minutes)
        # This is configured in settings but is critical for 0DTE success
        threshold_minutes = settings.TIME_GATE_MINUTES
        
        # Check if we've held the bias long enough
        if time_held_minutes < threshold_minutes:
            time_remaining = threshold_minutes - time_held_minutes
            
            self.logger.info(
                f"Time gate blocked bias change: held {current_bias} for {time_held_minutes} min, "
                f"need {threshold_minutes} min (0DTE rule)"
            )
            
            return {
                "passed": False,
                "type": "time_gate",
                "severity": "high",  # High severity for 0DTE
                "message": f"Bias change blocked - 0DTE {threshold_minutes}-minute rule",
                "current_value": f"{time_held_minutes} minutes",
                "threshold": f"{threshold_minutes} minutes",
                "time_remaining": f"{time_remaining} minutes",
                "guidance": (
                    f"Wait {time_remaining} more minutes. In 0DTE trading, patience is crucial. "
                    f"Options decay rapidly - frequent changes usually lead to losses."
                ),
            }
        
        # Time gate passed - bias has been held long enough
        return {
            "passed": True,
            "message": f"Time gate passed - {current_bias} bias held for {time_held_minutes} minutes",
        }