"""Simplified memory store implementation for trading decisions."""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union

from src.config import settings
from src.storage.redis_client import FixedRedisClient


class MemoryStore:
    """Simplified memory store for trading decisions and bias tracking."""
    
    def __init__(self):
        """Initialize memory store."""
        self.logger = logging.getLogger(__name__)
        self.redis = FixedRedisClient()
        
        # Valid decision types and bias values
        self.valid_decision_types = {
            "bias_establishment", "position_entry", "signal_blocked", 
            "session_close", "system_reset"
        }
        self.valid_bias_values = {"bullish", "bearish", "neutral"}
        self.valid_market_conditions = {"normal", "volatile", "choppy"}
    
    def _parse_datetime(self, dt_value: Any) -> Optional[datetime]:
        """Safely parse datetime from various formats."""
        if dt_value is None or str(dt_value).lower() == 'none':
            return None
        
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(dt_value)
            except ValueError:
                try:
                    # Try parsing as timestamp
                    return datetime.fromtimestamp(float(dt_value), tz=timezone.utc)
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not parse datetime: {dt_value}")
                    return None
        
        try:
            # Try converting to float (timestamp)
            return datetime.fromtimestamp(float(dt_value), tz=timezone.utc)
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse datetime: {dt_value}")
            return None
    
    def _serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    
    async def initialize(self) -> None:
        """Initialize storage connections."""
        await self.redis.initialize()
        self.logger.info("Memory store initialized")
    
    async def close(self) -> None:
        """Close storage connections."""
        await self.redis.close()
        self.logger.info("Memory store closed")
    
    async def health_check(self) -> bool:
        """Perform a health check on the memory store."""
        try:
            return self.redis.is_healthy
        except Exception as e:
            self.logger.error(f"Memory store health check failed: {e}")
            return False
    
    def _get_bias_key(self, symbol: str) -> str:
        """Get Redis key for bias data."""
        return f"bias:{symbol}"
    
    def _get_history_key(self, symbol: str) -> str:
        """Get Redis key for change history."""
        return f"changes:{symbol}"
    
    def _get_decisions_key(self, symbol: str) -> str:
        """Get Redis key for trading decisions."""
        return f"decisions:{symbol}"
    
    def _get_positions_key(self, symbol: str) -> str:
        """Get Redis key for position data."""
        return f"positions:{symbol}"
    
    def _get_session_key(self, date: str) -> str:
        """Get Redis key for session data."""
        return f"session:{date}"
    
    def _validate_bias_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple validation for bias data."""
        bias = data.get("bias")
        if bias not in self.valid_bias_values:
            raise ValueError(f"Invalid bias '{bias}'. Must be one of: {self.valid_bias_values}")
        
        reasoning = data.get("reasoning", "")
        if not reasoning or len(reasoning) < 10:
            raise ValueError("Reasoning must be at least 10 characters")
        
        confidence = data.get("confidence")
        if not isinstance(confidence, int) or not (1 <= confidence <= 100):
            raise ValueError("Confidence must be an integer between 1 and 100")
        
        market_condition = data.get("market_condition", "normal")
        if market_condition not in self.valid_market_conditions:
            raise ValueError(f"Invalid market condition '{market_condition}'. Must be one of: {self.valid_market_conditions}")
        
        # Check invalidation level for directional bias
        if bias in ["bullish", "bearish"] and data.get("invalidation_level") is None:
            raise ValueError(f"Invalidation level required for {bias} bias")
        
        return {
            "bias": bias,
            "reasoning": reasoning,
            "confidence": confidence,
            "invalidation_level": data.get("invalidation_level"),
            "market_condition": market_condition,
            "established_at": data.get("established_at"),
            "key_levels": data.get("key_levels")
        }
    
    def _validate_decision_content(self, decision_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Simple validation for decision content."""
        if decision_type == "bias_establishment":
            return self._validate_bias_data(content)
        
        elif decision_type == "position_entry":
            direction = content.get("direction")
            if direction not in ["long", "short"]:
                raise ValueError("Direction must be 'long' or 'short'")
            
            instrument = content.get("instrument", "")
            if not instrument or len(instrument) < 3:
                raise ValueError("Instrument must be at least 3 characters")
            
            entry_price = content.get("entry_price")
            if not isinstance(entry_price, (int, float)) or entry_price <= 0:
                raise ValueError("Entry price must be a positive number")
            
            size = content.get("size")
            if not isinstance(size, (int, float)) or size <= 0:
                raise ValueError("Size must be a positive number")
            
            reasoning = content.get("reasoning", "")
            if not reasoning or len(reasoning) < 10:
                raise ValueError("Reasoning must be at least 10 characters")
            
            return {
                "direction": direction,
                "instrument": instrument,
                "entry_price": entry_price,
                "size": size,
                "reasoning": reasoning,
                "linked_bias": content.get("linked_bias")
            }
        
        elif decision_type == "signal_blocked":
            proposed_bias = content.get("proposed_bias")
            if proposed_bias not in self.valid_bias_values:
                raise ValueError(f"Invalid proposed bias '{proposed_bias}'. Must be one of: {self.valid_bias_values}")
            
            proposed_reasoning = content.get("proposed_reasoning", "")
            if not proposed_reasoning or len(proposed_reasoning) < 5:
                raise ValueError("Proposed reasoning must be at least 5 characters")
            
            block_reason = content.get("block_reason")
            valid_block_reasons = {"time_gate", "whipsaw", "invalidation", "position"}
            if block_reason not in valid_block_reasons:
                raise ValueError(f"Invalid block reason '{block_reason}'. Must be one of: {valid_block_reasons}")
            
            return {
                "proposed_bias": proposed_bias,
                "proposed_reasoning": proposed_reasoning,
                "block_reason": block_reason,
                "block_details": content.get("block_details", {})
            }
        
        elif decision_type == "session_close":
            trades_count = content.get("trades_count", 0)
            if not isinstance(trades_count, int) or trades_count < 0:
                raise ValueError("Trades count must be a non-negative integer")
            
            decisions_count = content.get("decisions_count", 0)
            if not isinstance(decisions_count, int) or decisions_count < 0:
                raise ValueError("Decisions count must be a non-negative integer")
            
            summary = content.get("summary", "")
            if not summary or len(summary) < 10:
                raise ValueError("Summary must be at least 10 characters")
            
            return {
                "pnl": content.get("pnl"),
                "trades_count": trades_count,
                "decisions_count": decisions_count,
                "summary": summary,
                "key_learnings": content.get("key_learnings", [])
            }
        
        elif decision_type == "system_reset":
            symbol = content.get("symbol", "")
            if not symbol:
                raise ValueError("Symbol must be provided")
            
            reason = content.get("reason", "")
            if not reason or len(reason) < 5:
                raise ValueError("Reason must be at least 5 characters")
            
            return {
                "action": content.get("action", "force_reset"),
                "symbol": symbol,
                "reason": reason,
                "deleted_keys": content.get("deleted_keys", 0),
                "reset_at": content.get("reset_at", datetime.now(timezone.utc).isoformat())
            }
        
        else:
            raise ValueError(f"Unknown decision type: {decision_type}")
    
    async def get_current_bias(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current bias for symbol."""
        try:
            bias_data = await self.redis.get_json(self._get_bias_key(symbol))
            
            if bias_data:
                # Calculate time held using robust datetime parsing
                established_at = self._parse_datetime(bias_data.get("established_at"))
                
                if established_at:
                    now = datetime.now(timezone.utc)
                    time_held = now - established_at
                    time_held_minutes = int(time_held.total_seconds() / 60)
                    bias_data["time_held_minutes"] = time_held_minutes
                    # Ensure established_at is properly serialized
                    bias_data["established_at"] = self._serialize_datetime(established_at)
                else:
                    time_held_minutes = 0
                    bias_data["time_held_minutes"] = time_held_minutes
                    bias_data["established_at"] = self._serialize_datetime(datetime.now(timezone.utc))
                
                self.logger.debug(
                    f"Retrieved bias for {symbol}: {bias_data.get('bias')} held for {time_held_minutes} minutes"
                )
            
            return bias_data
            
        except Exception as e:
            self.logger.error(f"Failed to get current bias for {symbol}: {e}", exc_info=True)
            raise
    
    async def store_bias(self, symbol: str, bias_data: Dict[str, Any]) -> bool:
        """Store bias for symbol."""
        try:
            # Add timestamp if not present and ensure proper serialization
            if "established_at" not in bias_data:
                bias_data["established_at"] = self._serialize_datetime(datetime.now(timezone.utc))
            else:
                # Ensure existing timestamp is properly formatted
                dt = self._parse_datetime(bias_data["established_at"])
                if dt:
                    bias_data["established_at"] = self._serialize_datetime(dt)
            
            # Validate bias data
            validated_data = self._validate_bias_data(bias_data)
            
            # Store bias
            success = await self.redis.set_json(
                self._get_bias_key(symbol),
                validated_data,
                ex=settings.TTL_BIAS_DATA,
            )
            
            if success:
                # Add to history
                await self._add_to_history(symbol, {
                    "timestamp": validated_data["established_at"],
                    "type": "bias_change",
                    "from": await self._get_previous_bias(symbol),
                    "to": validated_data["bias"],
                    "reasoning": validated_data.get("reasoning"),
                    "confidence": validated_data.get("confidence"),
                    "invalidation_level": validated_data.get("invalidation_level"),
                })
            
            self.logger.info(
                f"Stored bias for {symbol}: {validated_data.get('bias')} "
                f"(confidence: {validated_data.get('confidence')}, "
                f"invalidation: {validated_data.get('invalidation_level')})"
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to store bias for {symbol}: {e}", exc_info=True)
            raise
    
    async def store_decision(
        self,
        symbol: str,
        decision_type: str,
        content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store trading decision with validation."""
        try:
            # Validate inputs
            if not symbol or not isinstance(symbol, str):
                raise ValueError("Symbol must be a non-empty string")
            
            if decision_type not in self.valid_decision_types:
                raise ValueError(f"Invalid decision type: {decision_type}. Must be one of {self.valid_decision_types}")
            
            # Validate content
            validated_content = self._validate_decision_content(decision_type, content)
            
            timestamp = datetime.now(timezone.utc).isoformat()
            decision_id = f"dec_{symbol.lower()}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            decision_data = {
                "decision_id": decision_id,
                "symbol": symbol.upper(),
                "decision_type": decision_type,
                "content": validated_content,
                "timestamp": timestamp,
            }
            
            # Route based on decision type
            storage_key = self._get_decisions_key(symbol)
            cross_references = ["symbol_history"]
            
            if decision_type == "bias_establishment":
                await self.store_bias(symbol, validated_content)
                storage_key = self._get_bias_key(symbol)
                cross_references = ["current_bias", "symbol_history"]
            
            elif decision_type == "position_entry":
                await self._store_position(symbol, validated_content)
                storage_key = self._get_positions_key(symbol)
                cross_references = ["current_bias", "symbol_history", "position_data"]
            
            elif decision_type == "signal_blocked":
                await self._store_blocked_signal(symbol, validated_content)
                storage_key = self._get_decisions_key(symbol)
                cross_references = ["current_bias", "symbol_history"]
            
            elif decision_type == "session_close":
                date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                await self._store_session_close(validated_content)
                storage_key = self._get_session_key(date)
                cross_references = ["session_data"]
            
            # Always store to decision history (except session_close)
            if decision_type != "session_close":
                await self.redis.push_to_list(
                    self._get_decisions_key(symbol),
                    decision_data,
                    max_length=settings.STORAGE_DECISION_LIMIT,
                )
                
                # Set expiry on decisions list
                await self.redis.set_expiry(
                    self._get_decisions_key(symbol), 
                    settings.TTL_DECISION_HISTORY
                )
            
            self.logger.info(f"Stored {decision_type} decision for {symbol} (ID: {decision_id})")
            
            # Calculate expiry time
            ttl_map = {
                "bias_establishment": settings.TTL_BIAS_DATA,
                "position_entry": settings.TTL_POSITION_DATA,
                "signal_blocked": settings.TTL_DECISION_HISTORY,
                "session_close": settings.TTL_SESSION_DATA,
            }
            
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=ttl_map.get(decision_type, settings.TTL_DECISION_HISTORY)
            )
            
            return {
                "success": True,
                "stored_at": timestamp,
                "decision_id": decision_id,
                "expires_at": expires_at.isoformat(),
                "storage_details": {
                    "redis_key": storage_key,
                    "history_updated": decision_type != "session_close",
                    "cross_references": cross_references
                }
            }
            
        except ValueError as e:
            self.logger.error(f"Validation error for {symbol} {decision_type}: {e}")
            return {
                "success": False,
                "error": "validation_failed",
                "message": str(e),
                "details": {
                    "field": "content",
                    "decision_type": decision_type
                }
            }
        
        except Exception as e:
            self.logger.error(f"Failed to store {decision_type} decision for {symbol}: {e}", exc_info=True)
            raise
    
    async def get_recent_changes(self, symbol: str, lookback_minutes: int) -> List[Dict[str, Any]]:
        """Get recent bias changes."""
        try:
            all_changes = await self.redis.get_list(self._get_history_key(symbol))
            
            # Filter by time
            cutoff_time = datetime.now(timezone.utc)
            recent_changes = []
            
            for change in all_changes:
                change_time = self._parse_datetime(change.get("timestamp"))
                if change_time:
                    time_diff = cutoff_time - change_time
                    if time_diff.total_seconds() <= lookback_minutes * 60:
                        recent_changes.append(change)
            
            return recent_changes
            
        except Exception as e:
            self.logger.error(f"Failed to get recent changes for {symbol}: {e}", exc_info=True)
            return []
    
    async def get_decision_history(
        self,
        symbol: str,
        limit: Optional[int] = None,
        decision_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get decision history for symbol."""
        try:
            all_decisions = await self.redis.get_list(
                self._get_decisions_key(symbol),
                end=limit - 1 if limit else -1
            )
            
            # Filter by decision type if specified
            if decision_type:
                all_decisions = [
                    d for d in all_decisions 
                    if d.get("decision_type") == decision_type
                ]
            
            return all_decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get decision history for {symbol}: {e}", exc_info=True)
            return []
    
    async def get_position_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Get position data for symbol."""
        try:
            return await self.redis.get_list(self._get_positions_key(symbol))
        except Exception as e:
            self.logger.error(f"Failed to get position data for {symbol}: {e}", exc_info=True)
            return []
    
    async def get_consistency_data(self, symbol: str, lookback_minutes: int = 60) -> Dict[str, Any]:
        """Get data needed for consistency checking."""
        try:
            # Get multiple pieces of data efficiently
            keys = [
                self._get_bias_key(symbol),
                self._get_positions_key(symbol),
            ]
            
            data = await self.redis.get_multiple_keys(keys)
            
            # Get recent changes separately
            recent_changes = await self.get_recent_changes(symbol, lookback_minutes)
            
            return {
                "current_bias": data.get(self._get_bias_key(symbol)),
                "recent_changes": recent_changes,
                "position_data": data.get(self._get_positions_key(symbol)) or [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get consistency data for {symbol}: {e}", exc_info=True)
            return {
                "current_bias": None,
                "recent_changes": [],
                "position_data": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    
    async def clear_symbol_data(self, symbol: str) -> bool:
        """Clear all data for a symbol."""
        try:
            keys_to_delete = [
                self._get_bias_key(symbol),
                self._get_history_key(symbol),
                self._get_decisions_key(symbol),
                self._get_positions_key(symbol),
            ]
            
            # Use atomic transaction to delete all keys
            operations = [("delete", (key,), {}) for key in keys_to_delete]
            results = await self.redis.atomic_transaction(operations)
            
            deleted_count = sum(1 for result in results if result)
            
            self.logger.info(f"Cleared data for {symbol}: {deleted_count}/{len(keys_to_delete)} keys deleted")
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"Failed to clear symbol data for {symbol}: {e}", exc_info=True)
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the memory store."""
        try:
            return {
                "redis_healthy": self.redis.is_healthy,
                "last_health_check": self.redis.last_health_check,
                "connection_pool_active": self.redis._pool is not None if hasattr(self.redis, '_pool') else False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get health status: {e}")
            return {
                "redis_healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _add_to_history(self, symbol: str, change_data: Dict[str, Any]) -> None:
        """Add entry to change history."""
        await self.redis.push_to_list(
            self._get_history_key(symbol),
            change_data,
            max_length=settings.STORAGE_HISTORY_LIMIT,
        )
        
        # Set expiry
        await self.redis.set_expiry(
            self._get_history_key(symbol), 
            settings.TTL_CHANGE_HISTORY
        )
    
    async def _get_previous_bias(self, symbol: str) -> Optional[str]:
        """Get previous bias from history."""
        history = await self.redis.get_list(self._get_history_key(symbol), 0, 0)
        if history and history[0].get("type") == "bias_change":
            return history[0].get("from")
        return None
    
    async def _store_position(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """Store position entry."""
        position_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        await self.redis.push_to_list(
            self._get_positions_key(symbol),
            position_data,
            max_length=settings.STORAGE_POSITION_LIMIT,
        )
        
        # Set expiry
        await self.redis.set_expiry(
            self._get_positions_key(symbol), 
            settings.TTL_POSITION_DATA
        )
    
    async def _store_blocked_signal(self, symbol: str, block_data: Dict[str, Any]) -> None:
        """Store blocked signal data."""
        # Add to history
        await self._add_to_history(symbol, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "signal_blocked",
            "proposed_bias": block_data.get("proposed_bias"),
            "block_reason": block_data.get("block_reason"),
        })
    
    async def _store_session_close(self, session_data: Dict[str, Any]) -> None:
        """Store session close data."""
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        session_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        await self.redis.set_json(
            self._get_session_key(date),
            session_data,
            ex=settings.TTL_SESSION_DATA,
        )