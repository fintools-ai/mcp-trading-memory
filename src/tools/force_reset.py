"""
Force Reset Tool

PURPOSE:
This tool provides an "emergency reset" capability for trading data when something
goes wrong with the memory system. Think of it as the "nuclear option" that wipes
all trading history and bias data for a symbol.

WHEN TO USE THIS TOOL:

1. CORRUPTED DATA:
   - Memory store has invalid or corrupted bias data
   - Inconsistent state between different data structures
   - Redis keys are malformed or contain bad data

2. SYSTEM RECOVERY:
   - After a system crash or unexpected shutdown
   - When consistency checkers are failing due to bad data
   - Memory store is in an unrecoverable state

3. FRESH START SCENARIOS:
   - Major market regime change (e.g., Fed policy shift)
   - Switching trading strategies completely
   - End of trading session with desire to clear all data

4. TESTING AND DEVELOPMENT:
   - Cleaning up after testing new features
   - Resetting demo accounts
   - Starting fresh simulation runs

WHAT THIS TOOL DOES:
1. Deletes ALL Redis keys associated with the symbol
2. Removes bias data, decision history, position records
3. Clears session data and recent changes history
4. Creates an audit trail of the reset operation
5. Logs the reset with timestamp and reason

WHAT GETS DELETED:
- bias:{symbol} - Current market bias and confidence
- history:{symbol} - All decision history
- position:{symbol} - Position entry records
- decisions:{symbol} - Trading decisions timeline
- changes:{symbol} - Recent bias changes for whipsaw detection
- session:{symbol} - Session summaries and PnL

DATA THAT SURVIVES:
- The reset operation itself is logged as a decision
- Audit trail of when and why the reset occurred
- System logs showing the reset event

WARNING - USE WITH EXTREME CAUTION:
- This operation is IRREVERSIBLE
- ALL trading memory for the symbol will be lost
- Consistency checkers will start fresh (no time gates, whipsaw protection)
- Any positions you have will lose their entry price tracking
- Learning from previous mistakes will be erased

SAFETY FEATURES:
- Requires explicit confirmation (confirm=true)
- Requires a reason for the reset
- Logs all reset operations with full context
- Creates audit trail for accountability

EXAMPLE USAGE:

Scenario 1 - Corrupted Data:
Input: {"symbol": "SPY", "confirm": true, "reason": "Corrupted bias data causing consistency failures"}
Output: All SPY data cleared, fresh start enabled

Scenario 2 - Strategy Change:
Input: {"symbol": "QQQ", "confirm": true, "reason": "Switching from scalping to swing trading strategy"}
Output: All QQQ memory cleared for new approach

Scenario 3 - Session End:
Input: {"symbol": "ES", "confirm": true, "reason": "End of trading day - clearing for tomorrow"}
Output: All ES data reset for next session

ALTERNATIVES TO CONSIDER FIRST:
- Individual decision corrections instead of full reset
- Temporary overrides for specific rules
- Manual bias adjustments
- Waiting for time gates to expire naturally

ONLY USE WHEN:
- Data is definitely corrupted
- No other recovery method works
- You understand the consequences
- You have a valid business reason
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import logging

from src.storage.memory_store import MemoryStore



class ForceResetTool:
    """
    Emergency tool for completely resetting all trading data for a symbol.
    
    This tool provides a "nuclear option" for clearing corrupted or unwanted
    trading memory. It should be used sparingly and only when other recovery
    methods have failed or when a complete fresh start is needed.
    
    The tool implements safety measures including required confirmation and
    detailed audit logging to prevent accidental data loss.
    """
    
    def __init__(self, memory_store: MemoryStore):
        """
        Initialize the force reset tool.
        
        Sets up connection to memory storage and logging. This tool has
        destructive capabilities so all operations are logged extensively.
        
        Args:
            memory_store: Redis storage containing all trading data
        """
        self.memory_store = memory_store
        self.logger = logging.getLogger(__name__)
        
        # Log tool initialization
        self.logger.info("Force reset tool initialized - use with extreme caution")
    
    @property
    def description(self) -> str:
        """Tool description emphasizing caution."""
        return "Emergency reset: completely wipes ALL trading data for a symbol (IRREVERSIBLE)"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol to completely reset (e.g., SPY, QQQ, AAPL)",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to proceed - safety check for irreversible operation",
                },
                "reason": {
                    "type": "string",
                    "description": "Detailed reason for reset (required for audit trail)",
                },
            },
            "required": ["symbol", "confirm", "reason"],
        }
    
    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the complete data reset for a trading symbol.
        
        This method performs a comprehensive deletion of all trading data
        associated with the symbol, including bias, history, positions,
        decisions, and session data. The operation is irreversible.
        
        Safety checks:
        1. Requires explicit confirmation flag
        2. Validates reason is provided
        3. Logs all operations for audit trail
        4. Creates reset record for accountability
        
        Args:
            args: Must contain symbol, confirm=true, and reason
            
        Returns:
            Success/failure result with details of what was deleted
        """
        symbol = args.get("symbol", "").upper().strip()
        confirm = args.get("confirm", False)
        reason = args.get("reason", "").strip()
        
        # Comprehensive input validation with security checks
        if not symbol:
            return {
                "success": False,
                "error": "Symbol required",
                "message": "Must provide a valid trading symbol to reset",
                "guidance": "Specify the exact symbol (e.g., SPY, QQQ) to reset",
            }
        
        if not confirm:
            return {
                "success": False,
                "error": "Reset not confirmed",
                "message": "This operation is IRREVERSIBLE - set confirm=true to proceed",
                "warning": "ALL trading data for this symbol will be permanently deleted",
                "guidance": "Only proceed if you understand the consequences",
            }
        
        if not reason or len(reason) < 10:
            return {
                "success": False,
                "error": "Detailed reason required",
                "message": "Must provide detailed reason (minimum 10 characters) for audit trail",
                "guidance": "Explain why this reset is necessary (e.g., 'corrupted data', 'strategy change')",
            }
        
        try:
            # Log the critical reset operation with full context
            self.logger.warning(
                f"FORCE RESET INITIATED for {symbol}: {reason}"
            )
            
            # Get current state before deletion for audit purposes
            try:
                current_bias = await self.memory_store.get_current_bias(symbol)
                self.logger.info(
                    f"Pre-reset state for {symbol}: "
                    f"bias={current_bias.get('bias') if current_bias else 'none'}"
                )
            except Exception as e:
                self.logger.warning(f"Could not retrieve pre-reset state for {symbol}: {e}")
            
            # Define ALL Redis keys that will be deleted
            # This is the complete list of data structures for a symbol
            keys_to_delete = [
                f"bias:{symbol}",      # Current market bias and confidence
                f"history:{symbol}",   # Complete decision history
                f"position:{symbol}",  # Position entry records
                f"decisions:{symbol}", # Detailed trading decisions
                f"changes:{symbol}",   # Recent bias changes for whipsaw detection
                f"session:{symbol}",   # Session summaries and PnL data
            ]
            
            self.logger.info(
                f"Preparing to delete {len(keys_to_delete)} Redis keys for {symbol}"
            )
            
            # Execute deletion of all symbol-related data
            deleted_count = 0
            deletion_details = []
            
            for key in keys_to_delete:
                try:
                    # Check if key exists before deletion
                    exists = await self.memory_store.redis.exists(key)
                    result = await self.memory_store.redis.delete(key)
                    
                    if result:
                        deleted_count += 1
                        deletion_details.append(f"{key} (existed: {bool(exists)})")
                        self.logger.debug(f"Deleted Redis key: {key}")
                    else:
                        deletion_details.append(f"{key} (not found)")
                        
                except Exception as e:
                    self.logger.error(f"Failed to delete key {key}: {e}")
                    deletion_details.append(f"{key} (delete failed: {e})")
            
            # Create comprehensive audit record of the reset operation
            reset_record = {
                "action": "force_reset",
                "symbol": symbol,
                "reason": reason,
                "deleted_keys_count": deleted_count,
                "deletion_details": deletion_details,
                "reset_at": datetime.now(timezone.utc).isoformat(),
                "total_keys_attempted": len(keys_to_delete),
                "success_rate": f"{(deleted_count/len(keys_to_delete)*100):.1f}%" if keys_to_delete else "0%",
            }
            
            # Store permanent audit trail of the reset operation
            # This is the ONLY data that survives the reset
            try:
                await self.memory_store.store_decision(
                    symbol=symbol,
                    decision_type="system_reset",
                    content=reset_record,
                )
                self.logger.info(f"Reset audit record stored for {symbol}")
            except Exception as e:
                # Even if audit fails, continue - don't block the reset
                self.logger.error(f"Failed to store reset audit record: {e}")
                reset_record["audit_storage_failed"] = str(e)
            
            # Log successful completion with full details
            self.logger.warning(
                f"FORCE RESET COMPLETED for {symbol}: {deleted_count}/{len(keys_to_delete)} keys deleted. "
                f"Reason: {reason}"
            )
            
            return {
                "success": True,
                "symbol": symbol,
                "deleted_keys_count": deleted_count,
                "total_keys_attempted": len(keys_to_delete),
                "deletion_details": deletion_details,
                "message": f"Complete reset successful: {deleted_count}/{len(keys_to_delete)} keys deleted for {symbol}",
                "reason": reason,
                "reset_timestamp": reset_record["reset_at"],
                "warning": "All trading memory has been permanently erased for this symbol",
                "next_steps": [
                    "Establish new bias if planning to trade this symbol",
                    "All consistency rules will start fresh (no time gates)",
                    "Position tracking has been reset",
                    "Consider this a completely clean slate"
                ],
            }
            
        except Exception as e:
            # Handle any unexpected errors during reset operation
            self.logger.error(
                f"FORCE RESET FAILED for {symbol}: {e}",
                exc_info=True
            )
            
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "message": f"Reset operation failed for {symbol} - data may be in inconsistent state",
                "reason": reason,
                "guidance": [
                    "Check Redis connectivity and permissions",
                    "Review logs for specific error details",
                    "Consider manual Redis key deletion if needed",
                    "Contact system administrator if error persists"
                ],
                "warning": "Symbol data may be partially deleted - verify state before trading",
            }