# MCP Trading Memory

Memory system for 0DTE options trading that prevents emotional mistakes and provides context for trading decisions.

## Problem Solved

**"LLM Trading Amnesia"** - Each trading query analyzed in isolation without context from previous decisions.

## Solution

4 tools that provide memory and consistency validation:
1. **get_current_bias** - Check existing market bias
2. **store_trading_decision** - Save trading decisions  
3. **check_consistency** - Validate against 3 rules (3min time gate, whipsaw protection, price movement stops)
4. **force_reset** - Clean slate when closing positions

## Installation

### Option 1: Editable Install (Recommended for Development)
```bash
# Clone the repository
git clone <repository-url>
cd mcp-trading-memory

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### Option 2: Direct Dependencies
```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Start Redis (required)
redis-server

# Run server (multiple ways):
mcp-trading-memory                    # If installed with pip install -e .
python3 src/server.py                # Direct execution
python3 -m src.server                # Module execution  
python3 run.py                       # Using run script

# Check installation
mcp-trading-memory --version
mcp-trading-memory --config-check
```

## 0DTE Configuration

```python
TIME_GATE_MINUTES = 3  # Fast decisions for 0DTE
WHIPSAW_MAX_CHANGES_PER_HOUR = 2
PRICE_MOVEMENT_THRESHOLDS = [5%, 10%, 20%]  # Stop loss levels
```

## Tool Examples

### 1. get_current_bias
Retrieve the current trading bias for a symbol.

**Request:**
```json
{
  "symbol": "SPY"
}
```

**Response (No Bias):**
```json
{
  "bias": null,
  "message": "No bias established for SPY",
  "suggestion": "Establish initial bias based on market analysis"
}
```

**Response (With Bias):**
```json
{
  "bias": "bullish",
  "confidence": 85,
  "invalidation_level": 475.0,
  "reasoning": "Strong breakout above 474 with volume confirmation",
  "established_at": "2024-01-15T09:35:00Z",
  "time_held_minutes": 47,
  "symbol": "SPY",
  "decision_count": 3
}
```

### 2. store_trading_decision
Store important trading decisions for continuity.

**Request (Bias Establishment):**
```json
{
  "symbol": "SPY",
  "decision_type": "bias_establishment",
  "content": {
    "bias": "bullish",
    "reasoning": "Breaking above key resistance at 474 with strong volume",
    "confidence": 85,
    "invalidation_level": 471.50
  }
}
```

**Response:**
```json
{
  "success": true,
  "decision_id": "dec_20240115_093500_bias_abc123",
  "symbol": "SPY",
  "decision_type": "bias_establishment",
  "stored_at": "2024-01-15T09:35:00Z",
  "message": "Bias establishment stored successfully"
}
```

**Request (Position Entry):**
```json
{
  "symbol": "SPY",
  "decision_type": "position_entry",
  "content": {
    "direction": "long",
    "instrument": "SPY 475 Call 0DTE",
    "entry_price": 2.45,
    "size": 10,
    "reasoning": "Confirmed breakout with momentum continuation"
  }
}
```

**Response:**
```json
{
  "success": true,
  "decision_id": "dec_20240115_094200_position_def456",
  "symbol": "SPY",
  "decision_type": "position_entry",
  "stored_at": "2024-01-15T09:42:00Z"
}
```

### 3. check_consistency
Validate trading decisions against consistency rules.

**Request:**
```json
{
  "symbol": "SPY",
  "proposed_bias": "bearish",
  "reasoning": "Seeing some pullback at resistance",
  "current_price": 474.80
}
```

**Response (Blocked by Time Gate):**
```json
{
  "consistent": false,
  "conflicts": [
    {
      "type": "time_gate",
      "severity": "high",
      "message": "Minimum holding period not met (2 of 3 minutes)",
      "current_value": 2,
      "threshold": 3,
      "time_remaining": "1 minute",
      "guidance": "Time gate protects against overtrading. Wait for the minimum holding period or use emergency override only in extreme market events."
    }
  ],
  "recommendation": "block_signal",
  "guidance": "TIME GATE ACTIVE: Wait 1 minute before bias change. This protection prevents costly overtrading in 0DTE options. Use this time to confirm your analysis and avoid emotional decisions.",
  "context": {
    "current_bias": "bullish",
    "established_at": "2024-01-15T09:35:00Z",
    "time_held": "2 minutes",
    "confidence": 85,
    "invalidation_level": 471.50,
    "recent_changes": 0
  }
}
```

**Response (All Rules Pass):**
```json
{
  "consistent": true,
  "conflicts": [],
  "recommendation": "proceed",
  "guidance": "SIGNAL APPROVED: All consistency rules passed. Proceed with confidence - timing and conditions are favorable.",
  "context": {
    "current_bias": "bullish",
    "time_held": "45 minutes",
    "recent_changes": 1
  }
}
```

### 4. force_reset
Emergency reset of all trading data for a symbol.

**Request:**
```json
{
  "symbol": "SPY",
  "confirm": true,
  "reason": "End of day cleanup - all positions closed"
}
```

**Response:**
```json
{
  "success": true,
  "symbol": "SPY",
  "deleted_keys_count": 6,
  "total_keys_attempted": 6,
  "message": "Complete reset successful: 6/6 keys deleted for SPY",
  "reason": "End of day cleanup - all positions closed",
  "reset_timestamp": "2024-01-15T16:00:00Z",
  "warning": "All trading memory has been permanently erased for this symbol",
  "next_steps": [
    "Establish new bias if planning to trade this symbol",
    "All consistency rules will start fresh (no time gates)",
    "Position tracking has been reset",
    "Consider this a completely clean slate"
  ]
}
```

**Request (Safety Check):**
```json
{
  "symbol": "SPY",
  "confirm": false,
  "reason": "Testing reset"
}
```

**Response:**
```json
{
  "success": false,
  "error": "Reset not confirmed",
  "message": "This operation is IRREVERSIBLE - set confirm=true to proceed",
  "warning": "ALL trading data for this symbol will be permanently deleted",
  "guidance": "Only proceed if you understand the consequences"
}
```

## Additional Examples

### Whipsaw Detection
**Request:**
```json
{
  "symbol": "QQQ",
  "proposed_bias": "bullish",
  "reasoning": "Market bouncing off support",
  "current_price": 425.50
}
```

**Response (Blocked by Whipsaw):**
```json
{
  "consistent": false,
  "conflicts": [
    {
      "type": "whipsaw",
      "severity": "high",
      "message": "Too many bias changes (3 in last 60 minutes)",
      "current_value": 3,
      "threshold": 2,
      "recent_changes": ["bullish->bearish", "bearish->neutral", "neutral->bearish"],
      "guidance": "Whipsaw protection prevents costly flip-flopping in indecisive markets. Wait for clearer directional signals or reduce position size."
    }
  ],
  "recommendation": "block_signal",
  "guidance": "🌊️ WHIPSAW DETECTED: 3 recent bias changes indicate choppy market. Wait for clearer directional signals or reduce position size. Chasing every market move leads to death by a thousand cuts."
}
```

### Invalidation Level Check
**Request:**
```json
{
  "symbol": "AAPL",
  "proposed_bias": "bearish",
  "reasoning": "Some selling pressure",
  "current_price": 182.50
}
```

**Response (Blocked by Invalidation):**
```json
{
  "consistent": false,
  "conflicts": [
    {
      "type": "invalidation",
      "severity": "medium",
      "message": "Price 182.50 still above invalidation 180.00",
      "current_value": 182.50,
      "threshold": 180.00,
      "guidance": "Invalidation levels enforce trading discipline. Current thesis remains valid until price definitively proves it wrong."
    }
  ],
  "recommendation": "block_signal",
  "guidance": "THESIS STILL VALID: Current price 182.50 hasn't breached invalidation level 180.00. Your original analysis remains correct until price proves otherwise. Be patient or provide strong fundamental reason for early exit."
}
```

### Session Close Decision
**Request:**
```json
{
  "symbol": "SPY",
  "decision_type": "session_close",
  "content": {
    "summary": "Profitable day with disciplined execution. Avoided 2 whipsaws.",
    "pnl": 1250.00,
    "trades_count": 3,
    "decisions_count": 8,
    "key_learnings": [
      "Time gate prevented costly flip at 10:30",
      "Invalidation level held perfectly at 471.50",
      "Patience paid off on the afternoon rally"
    ]
  }
}
```

**Response:**
```json
{
  "success": true,
  "decision_id": "dec_20240115_160000_session_xyz789",
  "symbol": "SPY",
  "decision_type": "session_close",
  "stored_at": "2024-01-15T16:00:00Z",
  "message": "Session close recorded successfully"
}
```

### Validation Errors
**Request (Invalid Symbol):**
```json
{
  "symbol": "INVALID SYMBOL",
  "proposed_bias": "bullish",
  "reasoning": "Testing invalid input"
}
```

**Response:**
```json
{
  "consistent": false,
  "error": "validation_failed",
  "message": "Invalid symbol format: INVALID SYMBOL. Must be 1-10 alphanumeric characters",
  "details": {
    "field": "symbol",
    "provided_value": "INVALID SYMBOL",
    "allowed_pattern": "alphanumeric characters only"
  }
}
```

## Documentation

See [TOOLS_WORKFLOW.md](TOOLS_WORKFLOW.md) for complete workflows with sequence diagrams.

## Architecture

- **FastMCP** server with Redis storage
- **Constants-based** configuration (no env vars)
- **0DTE optimized** with 3-minute time gates
- **Price movement protection** prevents chasing losses
- **Audit trail** for all trading decisions