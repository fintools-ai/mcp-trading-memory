"""
Store Trading Decision Tool

PURPOSE:
This tool stores critical trading decisions in the memory system to maintain
continuity and enable consistency checking. It's the "write" operation that
creates the trading history.

DECISION TYPES EXPLAINED:

1. BIAS_ESTABLISHMENT:
   - Sets or changes the market bias (bullish/bearish/neutral)
   - Requires: bias, confidence, reasoning, invalidation level
   - Example: "Establishing bullish bias on SPY due to breakout above resistance"

2. POSITION_ENTRY:
   - Records when a position is entered
   - Requires: direction, instrument, entry price, size, reasoning
   - Example: "Bought 10 SPY 450 calls at $2.50"

3. SIGNAL_BLOCKED:
   - Records when consistency rules prevent a trade
   - Requires: what was proposed, why it was blocked
   - Example: "Blocked bearish flip - time gate active for 2 more minutes"

4. SESSION_CLOSE:
   - End-of-day summary and learnings
   - Requires: summary, optionally PnL, trades, learnings
   - Example: "Closed session +$1,200, avoided 3 whipsaws"

WHY STORE DECISIONS?
- Creates audit trail for learning
- Enables consistency checking
- Prevents repeated mistakes
- Shows progression over time
"""

import logging
import re
from typing import Any, Dict, Optional

from src.storage.memory_store import MemoryStore


class StoreTradingDecisionTool:
    """
    Stores trading decisions in the memory system for future reference.
    
    This tool is critical for maintaining trading discipline - every important
    decision gets recorded, creating a permanent record that prevents the AI
    from forgetting or contradicting previous decisions.
    """
    
    def __init__(self, memory_store: MemoryStore):
        """
        Initialize with memory store connection.
        
        Args:
            memory_store: Redis storage for decisions
        """
        self.memory_store = memory_store
        self.logger = logging.getLogger(__name__)
    
    @property
    def description(self) -> str:
        """Tool description for the AI."""
        return "Store important trading decisions with full context"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Define expected input format."""
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol (e.g., SPY, QQQ, AAPL)",
                },
                "decision_type": {
                    "type": "string",
                    "enum": ["bias_establishment", "position_entry", "signal_blocked", "session_close"],
                    "description": "Type of decision being stored",
                },
                "content": {
                    "type": "object",
                    "description": "Decision content (structure varies by decision_type)",
                },
            },
            "required": ["symbol", "decision_type", "content"],
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a trading decision in memory.
        
        This method:
        1. Validates all inputs thoroughly
        2. Ensures content matches decision type requirements
        3. Stores in appropriate Redis structure
        4. Returns confirmation with decision ID
        
        Args:
            arguments: Contains symbol, decision_type, and content
            
        Returns:
            Success result with decision_id or error details
        """
        symbol = arguments.get("symbol", "").upper()
        decision_type = arguments.get("decision_type", "")
        content = arguments.get("content", {})
        
        # Validate symbol
        if not symbol:
            return {
                "success": False,
                "error": "validation_failed",
                "message": "Symbol is required",
                "details": {"field": "symbol", "issue": "missing_or_empty"},
            }
        
        # Symbol must be alphanumeric
        if not re.match(r'^[A-Z0-9]+$', symbol):
            return {
                "success": False,
                "error": "validation_failed",
                "message": "Invalid symbol format: must contain only letters and numbers",
                "details": {
                    "field": "symbol",
                    "provided_value": symbol,
                    "allowed_pattern": "alphanumeric characters only"
                },
            }
        
        # Validate decision type
        if not decision_type:
            return {
                "success": False,
                "error": "validation_failed",
                "message": "Decision type is required",
                "details": {"field": "decision_type", "issue": "missing_or_empty"},
            }
        
        allowed_types = ["bias_establishment", "position_entry", "signal_blocked", "session_close"]
        if decision_type not in allowed_types:
            return {
                "success": False,
                "error": "validation_failed",
                "message": f"Invalid decision type: must be one of {', '.join(allowed_types)}",
                "details": {
                    "field": "decision_type",
                    "provided_value": decision_type,
                    "allowed_values": allowed_types,
                },
            }
        
        # Content must exist
        if not content:
            return {
                "success": False,
                "error": "validation_failed",
                "message": "Content is required",
                "details": {"field": "content", "issue": "missing_or_empty"},
            }
        
        # Validate content structure based on decision type
        validation_result = self._validate_content(decision_type, content)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "validation_failed",
                "message": validation_result["message"],
                "details": validation_result["details"],
            }
        
        try:
            # Store the decision
            result = await self.memory_store.store_decision(symbol, decision_type, content)
            
            self.logger.info(
                f"Stored {decision_type} decision for {symbol} "
                f"(ID: {result.get('decision_id')})"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(
                f"Failed to store {decision_type} for {symbol}: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "error": "storage_failed",
                "message": "Failed to store decision in memory",
                "details": {"error": str(e)},
            }
    
    def _validate_content(self, decision_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route to appropriate validation based on decision type.
        
        Each decision type has specific required fields and validation rules.
        """
        if decision_type == "bias_establishment":
            return self._validate_bias_establishment(content)
        elif decision_type == "position_entry":
            return self._validate_position_entry(content)
        elif decision_type == "signal_blocked":
            return self._validate_signal_blocked(content)
        elif decision_type == "session_close":
            return self._validate_session_close(content)
        
        return {"valid": True}
    
    def _validate_bias_establishment(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate bias establishment content.
        
        Required fields:
        - bias: bullish/bearish/neutral
        - confidence: 1-100 score
        - reasoning: Why this bias (min 10 chars)
        - invalidation_level: Price that proves bias wrong (for directional bias)
        """
        # Check bias value
        bias = content.get("bias")
        if not bias:
            return {
                "valid": False,
                "message": "Bias is required for bias establishment",
                "details": {"field": "content.bias", "issue": "missing"},
            }
        
        allowed_biases = ["bullish", "bearish", "neutral"]
        if bias not in allowed_biases:
            return {
                "valid": False,
                "message": f"Invalid bias value: must be bullish, bearish, or neutral",
                "details": {
                    "field": "content.bias",
                    "provided_value": bias,
                    "allowed_values": allowed_biases,
                },
            }
        
        # Directional bias needs invalidation level
        if bias in ["bullish", "bearish"]:
            invalidation_level = content.get("invalidation_level")
            if invalidation_level is None:
                return {
                    "valid": False,
                    "message": f"Invalidation level required for {bias} bias",
                    "details": {"field": "content.invalidation_level", "issue": "missing"},
                }
            
            if not isinstance(invalidation_level, (int, float)):
                return {
                    "valid": False,
                    "message": "Invalidation level must be a number",
                    "details": {
                        "field": "content.invalidation_level", 
                        "provided_value": invalidation_level,
                        "expected_type": "number"
                    },
                }
        
        # Check confidence score
        confidence = content.get("confidence")
        if confidence is None:
            return {
                "valid": False,
                "message": "Confidence score is required",
                "details": {"field": "content.confidence", "issue": "missing"},
            }
        
        if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 100):
            return {
                "valid": False,
                "message": "Confidence must be a number between 1 and 100",
                "details": {
                    "field": "content.confidence", 
                    "provided_value": confidence,
                    "valid_range": "1-100"
                },
            }
        
        # Check reasoning
        reasoning = content.get("reasoning")
        if not reasoning or not isinstance(reasoning, str):
            return {
                "valid": False,
                "message": "Reasoning is required and must be a non-empty string",
                "details": {"field": "content.reasoning", "issue": "missing_or_invalid"},
            }
        
        if len(reasoning) < 10:
            return {
                "valid": False,
                "message": "Reasoning must be at least 10 characters long",
                "details": {
                    "field": "content.reasoning", 
                    "provided_length": len(reasoning),
                    "minimum_length": 10
                },
            }
        
        return {"valid": True}
    
    def _validate_position_entry(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate position entry content.
        
        Required fields:
        - direction: long or short
        - instrument: What's being traded (e.g., "SPY 450 Call")
        - entry_price: Price paid
        - size: Position size
        - reasoning: Why entering now
        """
        # Define required fields and their validators
        required_validations = {
            "direction": {
                "validator": lambda x: isinstance(x, str) and x.lower() in ["long", "short"],
                "message": "Direction must be 'long' or 'short'",
                "allowed_values": ["long", "short"]
            },
            "instrument": {
                "validator": lambda x: isinstance(x, str) and len(x) >= 3,
                "message": "Instrument must be a string with at least 3 characters",
            },
            "entry_price": {
                "validator": lambda x: isinstance(x, (int, float)) and x > 0,
                "message": "Entry price must be a positive number",
            },
            "size": {
                "validator": lambda x: isinstance(x, (int, float)) and x > 0,
                "message": "Size must be a positive number",
            },
            "reasoning": {
                "validator": lambda x: isinstance(x, str) and len(x) >= 10,
                "message": "Reasoning must be a string with at least 10 characters",
            }
        }
        
        # Check each required field
        for field, validation in required_validations.items():
            value = content.get(field)
            if value is None:
                return {
                    "valid": False,
                    "message": f"{field.replace('_', ' ').title()} is required for position entry",
                    "details": {"field": f"content.{field}", "issue": "missing"},
                }
            
            if not validation["validator"](value):
                details = {
                    "field": f"content.{field}",
                    "provided_value": value,
                }
                if "allowed_values" in validation:
                    details["allowed_values"] = validation["allowed_values"]
                
                return {
                    "valid": False,
                    "message": validation["message"],
                    "details": details,
                }
        
        return {"valid": True}
    
    def _validate_signal_blocked(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate blocked signal content.
        
        Records when consistency rules prevent a trade.
        Required:
        - proposed_bias: What was attempted
        - proposed_reasoning: Why it was attempted
        - block_reason: Which rule blocked it (time_gate/whipsaw/invalidation/position)
        - block_details: Additional context (optional)
        """
        required_fields = {
            "proposed_bias": {
                "validator": lambda x: isinstance(x, str) and x in ["bullish", "bearish", "neutral"],
                "message": "Proposed bias must be bullish, bearish, or neutral",
                "allowed_values": ["bullish", "bearish", "neutral"]
            },
            "proposed_reasoning": {
                "validator": lambda x: isinstance(x, str) and len(x) >= 5,
                "message": "Proposed reasoning must be a string with at least 5 characters",
            },
            "block_reason": {
                "validator": lambda x: isinstance(x, str) and x in ["time_gate", "whipsaw", "invalidation", "position"],
                "message": "Block reason must be one of: time_gate, whipsaw, invalidation, position",
                "allowed_values": ["time_gate", "whipsaw", "invalidation", "position"]
            }
        }
        
        # Validate required fields
        for field, validation in required_fields.items():
            value = content.get(field)
            if value is None:
                return {
                    "valid": False,
                    "message": f"{field.replace('_', ' ').title()} is required for blocked signal",
                    "details": {"field": f"content.{field}", "issue": "missing"},
                }
            
            if not validation["validator"](value):
                details = {
                    "field": f"content.{field}",
                    "provided_value": value,
                }
                if "allowed_values" in validation:
                    details["allowed_values"] = validation["allowed_values"]
                
                return {
                    "valid": False,  
                    "message": validation["message"],
                    "details": details,
                }
        
        # Optional block_details must be dict if provided
        block_details = content.get("block_details", {})
        if block_details and not isinstance(block_details, dict):
            return {
                "valid": False,
                "message": "Block details must be a dictionary",
                "details": {
                    "field": "content.block_details",
                    "provided_type": type(block_details).__name__,
                    "expected_type": "dict"
                },
            }
        
        return {"valid": True}
    
    def _validate_session_close(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate session close content.
        
        End-of-day summary. Required:
        - summary: What happened today (min 10 chars)
        
        Optional:
        - pnl: Profit/loss for the day
        - trades_count: Number of trades executed
        - decisions_count: Number of decisions made
        - key_learnings: List of lessons learned
        """
        if not content:
            return {
                "valid": False,
                "message": "Session close content cannot be empty",
                "details": {"field": "content", "issue": "empty"},
            }
        
        # Summary is required
        summary = content.get("summary")
        if not summary or not isinstance(summary, str):
            return {
                "valid": False,
                "message": "Summary is required for session close",
                "details": {"field": "content.summary", "issue": "missing_or_invalid"},
            }
        
        if len(summary) < 10:
            return {
                "valid": False,
                "message": "Summary must be at least 10 characters long",
                "details": {
                    "field": "content.summary",
                    "provided_length": len(summary),
                    "minimum_length": 10
                },
            }
        
        # Validate optional numeric fields
        trades_count = content.get("trades_count")
        if trades_count is not None and (not isinstance(trades_count, int) or trades_count < 0):
            return {
                "valid": False,
                "message": "Trades count must be a non-negative integer",
                "details": {
                    "field": "content.trades_count",
                    "provided_value": trades_count,
                    "expected_type": "non-negative integer"
                },
            }
        
        decisions_count = content.get("decisions_count")
        if decisions_count is not None and (not isinstance(decisions_count, int) or decisions_count < 0):
            return {
                "valid": False,
                "message": "Decisions count must be a non-negative integer",
                "details": {
                    "field": "content.decisions_count",
                    "provided_value": decisions_count,
                    "expected_type": "non-negative integer"
                },
            }
        
        pnl = content.get("pnl")
        if pnl is not None and not isinstance(pnl, (int, float)):
            return {
                "valid": False,
                "message": "PnL must be a number",
                "details": {
                    "field": "content.pnl",
                    "provided_value": pnl,
                    "expected_type": "number"
                },
            }
        
        # Key learnings must be a list
        key_learnings = content.get("key_learnings")
        if key_learnings is not None and not isinstance(key_learnings, list):
            return {
                "valid": False,
                "message": "Key learnings must be a list",
                "details": {
                    "field": "content.key_learnings",
                    "provided_type": type(key_learnings).__name__,
                    "expected_type": "list"
                },
            }
        
        return {"valid": True}