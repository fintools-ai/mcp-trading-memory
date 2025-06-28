"""
Check Consistency Tool

PURPOSE:
This tool acts as the "trading police" - it enforces discipline by checking every proposed
bias change against three critical consistency rules. Think of it as your risk management
partner that prevents emotional or impulsive trading decisions.

THE THREE CONSISTENCY RULES:

1. TIME GATE (Prevents Overtrading):
   - For 0DTE options: Minimum 5-minute holding period between bias changes
   - Prevents rapid flip-flopping that leads to death by a thousand cuts
   - Can be overridden in extreme market conditions (use sparingly)
   
2. WHIPSAW PROTECTION (Prevents Chasing Markets):
   - Detects when you've changed bias too many times in the last hour
   - Default: Maximum 3 bias changes per hour
   - Prevents getting chopped up in sideways/indecisive markets
   
3. INVALIDATION LEVEL CHECK (Enforces Discipline):
   - Prevents changing bias until your current thesis is proven wrong
   - Uses price levels to determine if bias change is justified
   - Adds buffer to prevent whipsaws around exact levels

WHY THESE RULES MATTER:
- Emotional trading is the #1 destroyer of 0DTE accounts
- 0DTE options are extremely sensitive to timing and direction
- Small hesitations or wrong moves can wipe out entire account
- These rules keep you from being your own worst enemy

HOW IT WORKS:
1. You propose a bias change (bullish to bearish, etc.)
2. Tool checks all three rules against your trading history
3. Returns PASS (proceed) or BLOCK (wait/reconsider) with specific guidance
4. If blocked, provides exact time remaining or conditions needed to proceed

EXAMPLE SCENARIOS:

Scenario 1 - Time Gate Block:
Input: Change SPY from bullish to bearish (held for 2 minutes)
Output: BLOCKED - "Wait 3 more minutes before bias change (time gate active)"

Scenario 2 - Whipsaw Block:
Input: Change QQQ bias (3rd change in past hour)
Output: BLOCKED - "Too many bias changes (3/3 limit). Wait 45 minutes or market must show clear direction."

Scenario 3 - Invalidation Block:
Input: Change from bullish to bearish, current price $425, invalidation at $420
Output: BLOCKED - "Bullish thesis still valid. Price $425 above invalidation $420. Wait for break or provide strong fundamental reason."

Scenario 4 - All Rules Pass:
Input: Change from bullish to bearish after holding for 10 minutes, price broke below invalidation
Output: APPROVED - "Signal change approved - all consistency rules passed"

THIS TOOL SAVES YOU FROM:
- Overtrading and high commission costs
- Emotional flip-flopping in volatile markets
- Abandoning winning strategies too early
- Chasing every market wiggle
- Turning small losses into account killers

USE CASES:
- Before entering any new position
- Before closing existing positions early
- Before changing market bias
- When feeling emotional about a trade
- In fast-moving or uncertain markets
"""

import time
from typing import Any, Dict, List, Optional

import logging

from src.config import settings
from src.consistency.invalidation_checker import InvalidationChecker
from src.consistency.time_gate import TimeGate
from src.consistency.whipsaw_detector import WhipsawDetector
from src.storage.memory_store import MemoryStore



class CheckConsistencyTool:
    """
    Validates new trading signals against established consistency rules.
    
    This tool implements the core discipline enforcement system that prevents
    emotional trading and ensures systematic decision-making. It acts as an
    objective referee that applies consistent rules regardless of market emotions.
    
    The tool combines three different checking mechanisms:
    - TimeGate: Enforces minimum holding periods
    - WhipsawDetector: Prevents excessive bias changes
    - InvalidationChecker: Enforces thesis validation
    """
    
    def __init__(self, memory_store: MemoryStore):
        """
        Initialize the consistency checking tool.
        
        Sets up all three consistency checkers and logging. Each checker
        is responsible for one aspect of trading discipline:
        - TimeGate: Minimum holding periods
        - WhipsawDetector: Bias change frequency limits  
        - InvalidationChecker: Price level validation
        
        Args:
            memory_store: Redis storage containing trading history
        """
        self.memory_store = memory_store
        self.logger = logging.getLogger(__name__)
        
        # Initialize the three consistency enforcement systems
        self.time_gate = TimeGate()
        self.whipsaw_detector = WhipsawDetector()
        self.invalidation_checker = InvalidationChecker()
        
        self.logger.debug("Initialized consistency checker with all three rule engines")
    
    @property
    def description(self) -> str:
        """Tool description for the AI system."""
        return "Validates trading signals against time gate, whipsaw, and invalidation rules"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol to check consistency for (e.g., SPY, QQQ, AAPL)",
                },
                "proposed_bias": {
                    "type": "string",
                    "enum": ["bullish", "bearish", "neutral"],
                    "description": "Proposed new market bias - what you want to change to",
                },
                "reasoning": {
                    "type": "string", 
                    "description": "Detailed explanation for why you want to change bias (minimum 10 chars)",
                },
                "proposed_action": {
                    "type": "string",
                    "description": "Specific trading action (optional): buy_calls, sell_puts, close_position, etc.",
                },
                "override_time_gate": {
                    "type": "boolean",
                    "default": False,
                    "description": "Emergency override for time gate (use only in extreme market events)",
                },
                "market_condition": {
                    "type": "string",
                    "enum": ["normal", "volatile", "choppy"],
                    "default": "normal",
                    "description": "Current market environment affects rule strictness",
                },
                "current_price": {
                    "type": "number",
                    "description": "Current market price for invalidation level checks (required for price-based rules)",
                },
            },
            "required": ["symbol", "proposed_bias", "reasoning"],
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute comprehensive consistency checking against all three rules.
        
        This method orchestrates the entire consistency checking process:
        1. Validates all input parameters
        2. Retrieves current market context from memory
        3. Applies each consistency rule in sequence
        4. Aggregates results and provides clear guidance
        
        The method returns detailed feedback about what passed/failed and
        exactly what needs to happen before the signal can be approved.
        
        Args:
            arguments: Input parameters including symbol, proposed bias, reasoning
            
        Returns:
            Comprehensive result including:
            - consistent: True if all rules pass, False if any fail
            - conflicts: List of specific rule violations with guidance
            - recommendation: "proceed" or "block_signal"
            - guidance: Human-readable advice on next steps
            - context: Current trading state information
            - debug_info: Technical details for troubleshooting
        """
        symbol = arguments.get("symbol", "").upper()
        proposed_bias = arguments.get("proposed_bias", "")
        reasoning = arguments.get("reasoning", "")
        override_time_gate = arguments.get("override_time_gate", False)
        market_condition = arguments.get("market_condition", "normal")
        current_price = arguments.get("current_price")
        
        # Comprehensive input validation with detailed error messages
        if not symbol:
            return {
                "consistent": False,
                "error": "Symbol is required",
                "guidance": "Provide a valid trading symbol (e.g., SPY, QQQ, AAPL)",
            }
        
        if not proposed_bias:
            return {
                "consistent": False,
                "error": "Proposed bias is required",
                "guidance": "Specify the desired bias: bullish, bearish, or neutral",
            }
        
        if proposed_bias not in ["bullish", "bearish", "neutral"]:
            return {
                "consistent": False,
                "error": f"Invalid proposed bias: {proposed_bias}",
                "guidance": "Bias must be exactly 'bullish', 'bearish', or 'neutral'",
            }
        
        if not reasoning or len(reasoning.strip()) < 10:
            return {
                "consistent": False,
                "error": "Detailed reasoning is required (minimum 10 characters)",
                "guidance": "Provide specific market analysis justifying the bias change",
            }
        
        # Enhanced validation for challenging market conditions
        if market_condition == "choppy" and len(reasoning.strip()) < 50:
            return {
                "consistent": False,
                "error": "Choppy market conditions require detailed reasoning (minimum 50 characters)",
                "guidance": (
                    "In choppy markets, bias changes are extremely risky. Provide detailed "
                    "technical analysis and multiple confirming signals before proceeding."
                ),
                "current_reasoning_length": len(reasoning.strip()),
                "required_length": 50,
            }
        
        # Track processing time
        start_time = time.time()
        
        try:
            # Retrieve comprehensive market context from memory store
            # This includes current bias, timing, confidence levels, and recent activity
            current_bias_data = await self.memory_store.get_current_bias(symbol)
            recent_changes = await self.memory_store.get_recent_changes(
                symbol, settings.WHIPSAW_LOOKBACK_MINUTES
            )
            
            current_bias = current_bias_data.get("bias") if current_bias_data else None
            
            self.logger.debug(
                f"Retrieved context for {symbol}: current_bias={current_bias}, "
                f"recent_changes={len(recent_changes)}, proposed_bias={proposed_bias}"
            )
            
            # Apply all three consistency rules in sequence
            # Each rule can add conflicts to the list with specific guidance
            conflicts = []
            
            self.logger.info(
                f"Starting consistency check for {symbol}: {current_bias} -> {proposed_bias}"
            )
            
            # RULE 1: TIME GATE CHECK
            # Prevents overtrading by enforcing minimum holding periods
            # Critical for 0DTE options where rapid changes are costly
            time_gate_result = await self.time_gate.check(
                current_bias_data,
                proposed_bias,
                market_condition,
                override_time_gate,
            )
            if not time_gate_result["passed"]:
                self.logger.warning(
                    f"Time gate violation for {symbol}: {time_gate_result.get('message')}"
                )
                
                conflict = {
                    "type": "time_gate",
                    "severity": time_gate_result.get("severity", "high"),
                    "message": time_gate_result.get("message"),
                    "current_value": time_gate_result.get("current_value"),
                    "threshold": time_gate_result.get("threshold"),
                    "time_remaining": time_gate_result.get("time_remaining"),
                    "guidance": (
                        "Time gate protects against overtrading. Wait for the minimum "
                        "holding period or use emergency override only in extreme market events."
                    ),
                }
                conflicts.append(conflict)
            
            # RULE 2: WHIPSAW PROTECTION
            # Detects excessive bias changes that indicate chasing markets
            # Protects against being chopped up in indecisive markets
            whipsaw_result = await self.whipsaw_detector.check(
                recent_changes,
                proposed_bias,
                current_bias,
                market_condition,
            )
            if not whipsaw_result["passed"]:
                self.logger.warning(
                    f"Whipsaw detected for {symbol}: {whipsaw_result.get('message')}"
                )
                
                conflict = {
                    "type": "whipsaw",
                    "severity": whipsaw_result.get("severity", "high"),
                    "message": whipsaw_result.get("message"),
                    "current_value": whipsaw_result.get("current_value"),
                    "threshold": whipsaw_result.get("threshold"),
                    "guidance": (
                        "Whipsaw protection prevents costly flip-flopping in indecisive markets. "
                        "Wait for clearer directional signals or reduce position size."
                    ),
                }
                # Add detailed whipsaw analysis if available
                if "recent_changes" in whipsaw_result:
                    conflict["recent_changes"] = whipsaw_result["recent_changes"]
                if "pattern" in whipsaw_result:
                    conflict["pattern"] = whipsaw_result["pattern"]
                conflicts.append(conflict)
            
            # RULE 3: INVALIDATION LEVEL CHECK
            # Ensures bias changes only occur when thesis is proven wrong by price action
            # Enforces systematic exits rather than emotional decisions
            if current_price is not None:
                invalidation_result = await self.invalidation_checker.check(
                    current_bias_data,
                    proposed_bias,
                    current_price,
                    memory_store=self.memory_store,
                    symbol=symbol,
                )
                if not invalidation_result["passed"]:
                    self.logger.warning(
                        f"Invalidation check failed for {symbol}: {invalidation_result.get('message')}"
                    )
                    
                    conflict = {
                        "type": "invalidation",
                        "severity": invalidation_result.get("severity", "medium"),
                        "message": invalidation_result.get("message"),
                        "current_value": invalidation_result.get("current_value"),
                        "threshold": invalidation_result.get("threshold"),
                        "guidance": (
                            "Invalidation levels enforce trading discipline. Current thesis "
                            "remains valid until price definitively proves it wrong."
                        ),
                    }
                    conflicts.append(conflict)
            else:
                # No current price provided - warn but don't block
                self.logger.info(
                    f"No current price provided for {symbol} - skipping invalidation check"
                )
            
            
            # Aggregate results and determine final recommendation
            consistent = len(conflicts) == 0
            recommendation = "proceed" if consistent else "block_signal"
            
            # Generate specific, actionable guidance based on conflicts
            guidance = self._generate_guidance(conflicts, current_bias_data, proposed_bias)
            
            # Log the final decision
            if consistent:
                self.logger.info(
                    f"Consistency check PASSED for {symbol}: {current_bias} -> {proposed_bias}"
                )
            else:
                self.logger.warning(
                    f"Consistency check BLOCKED for {symbol}: {len(conflicts)} rule violations"
                )
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Compile comprehensive result with all context and debugging info
            result = {
                "consistent": consistent,
                "conflicts": conflicts,
                "recommendation": recommendation,
                "guidance": guidance,
                "context": {
                    "current_bias": current_bias,
                    "proposed_bias": proposed_bias,
                    "established_at": current_bias_data.get("established_at") if current_bias_data else None,
                    "time_held": f"{current_bias_data.get('time_held_minutes', 0)} minutes" if current_bias_data else "N/A",
                    "confidence": current_bias_data.get("confidence") if current_bias_data else None,
                    "invalidation_level": current_bias_data.get("invalidation_level") if current_bias_data else None,
                    "recent_changes": len(recent_changes),
                    "market_condition": market_condition,
                    "reasoning_provided": len(reasoning.strip()) if reasoning else 0,
                },
                "debug_info": {
                    "rules_checked": ["time_gate", "whipsaw", "invalidation"],
                    "current_price": current_price,
                    "processing_time_ms": processing_time_ms,
                    "override_time_gate": override_time_gate,
                    "rules_passed": 3 - len(conflicts),
                    "rules_failed": len(conflicts),
                },
            }
            
            # Log detailed completion summary
            self.logger.info(
                f"Consistency check completed for {symbol}: "
                f"{current_bias} -> {proposed_bias} = {'PASS' if consistent else 'BLOCK'} "
                f"({len(conflicts)} conflicts in {processing_time_ms}ms)"
            )
            
            return result
        
        except Exception as e:
            # Handle any unexpected errors during consistency checking
            self.logger.error(
                f"Consistency check failed for {symbol}: {e}",
                exc_info=True
            )
            
            return {
                "consistent": False,
                "error": "consistency_check_failed",
                "message": "Unable to perform consistency check due to system error",
                "details": str(e),
                "fallback": (
                    "System error prevented consistency verification. "
                    "Proceed with extreme caution or wait for system recovery."
                ),
                "guidance": (
                    "When consistency checks fail, consider: 1) Reducing position size, "
                    "2) Waiting for system recovery, 3) Manual rule verification, "
                    "4) Avoiding complex strategies until system is restored."
                ),
            }
    
    def _generate_guidance(
        self,
        conflicts: List[Dict],
        current_bias_data: Optional[Dict],
        proposed_bias: str,
    ) -> str:
        """
        Generate specific, actionable guidance based on consistency check results.
        
        This method prioritizes conflicts and provides clear next steps. Guidance
        is ordered by rule priority: Time Gate (highest), Whipsaw, Invalidation.
        
        For successful checks, encourages proceeding with the validated signal.
        For conflicts, provides specific timing and conditions for approval.
        
        Args:
            conflicts: List of specific rule violations with details
            current_bias_data: Current market bias context
            proposed_bias: Desired new bias
            
        Returns:
            Clear, actionable guidance message with specific next steps
        """
        if not conflicts:
            return (
                "🟢 SIGNAL APPROVED: All consistency rules passed. "
                "Proceed with confidence - timing and conditions are favorable."
            )
        
        # Generate prioritized guidance - Time Gate has highest priority
        # as it prevents the most dangerous overtrading patterns
        time_gate_conflicts = [c for c in conflicts if c.get("type") == "time_gate"]
        if time_gate_conflicts:
            conflict = time_gate_conflicts[0]
            time_remaining = conflict.get("time_remaining", "unknown")
            return (
                f"⏰ TIME GATE ACTIVE: Wait {time_remaining} before bias change. "
                f"This protection prevents costly overtrading in 0DTE options. "
                f"Use this time to confirm your analysis and avoid emotional decisions."
            )
        
        # Whipsaw protection has second priority
        whipsaw_conflicts = [c for c in conflicts if c.get("type") == "whipsaw"]
        if whipsaw_conflicts:
            conflict = whipsaw_conflicts[0]
            changes = conflict.get("current_value", "multiple")
            return (
                f"🌪️ WHIPSAW DETECTED: {changes} recent bias changes indicate choppy market. "
                f"Wait for clearer directional signals or reduce position size. "
                f"Chasing every market move leads to death by a thousand cuts."
            )
        
        # Invalidation conflicts indicate thesis is still valid
        invalidation_conflicts = [c for c in conflicts if c.get("type") == "invalidation"]
        if invalidation_conflicts:
            conflict = invalidation_conflicts[0]
            threshold = conflict.get("threshold")
            current_value = conflict.get("current_value")
            if threshold and isinstance(threshold, (int, float)):
                return (
                    f"📊 THESIS STILL VALID: Current price {current_value} hasn't breached "
                    f"invalidation level {threshold:.2f}. Your original analysis remains "
                    f"correct until price proves otherwise. Be patient or provide strong "
                    f"fundamental reason for early exit."
                )
            else:
                return (
                    "📊 INVALIDATION CHECK: Your current thesis hasn't been proven wrong yet. "
                    "Wait for clear invalidation signal or provide compelling fundamental "
                    "analysis for bias change."
                )
        
        # Multiple conflicts require comprehensive review
        conflict_types = [c.get("type", "unknown") for c in conflicts]
        return (
            f"🚫 MULTIPLE RULE VIOLATIONS: {', '.join(conflict_types)} conflicts detected. "
            f"This suggests either poor timing or emotional decision-making. "
            f"Review each conflict carefully and wait for better market conditions."
        )