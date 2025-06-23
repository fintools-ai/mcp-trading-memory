
## What is the main problem
- We need to solve "LLM trading amnesia" - the core problem where each query is analyzed in isolation without context from previous decisions.

- The goal is to build tools which can solve this problem, I'm going to allow LLM to invoke memory tools

## Integration Flow with Trade Copilot

### Complete Request-Response Cycle with Detailed Tool Calls

```mermaid
sequenceDiagram
    participant User
    participant TradeCopilot
    participant MemoryMCP
    participant MarketDataMCPs
    participant Redis
    
    User->>TradeCopilot: "Should I buy SPY calls?"
    
    Note over TradeCopilot: Step 1: Check Memory Context
    TradeCopilot->>MemoryMCP: get_current_bias({"symbol": "SPY"})
    MemoryMCP->>Redis: GET bias:SPY
    Redis-->>MemoryMCP: {bias: "bullish", established_at: "09:45Z", confidence: 85}
    MemoryMCP-->>TradeCopilot: Bullish bias active (23 min), invalidation: 471.50
    
    Note over TradeCopilot: Step 2: Get Fresh Market Data
    TradeCopilot->>MarketDataMCPs: get_market_data("SPY")
    MarketDataMCPs-->>TradeCopilot: {price: 472.80, volume: 1.2M, above_vwap: true}
    
    Note over TradeCopilot: Step 3: AI Analysis with Context
    TradeCopilot->>TradeCopilot: Analysis: Bullish bias + above VWAP = BUY CALLS
    
    Note over TradeCopilot: Step 4: Consistency Validation
    TradeCopilot->>MemoryMCP: check_consistency({"symbol": "SPY", "proposed_bias": "bullish", "proposed_action": "buy_calls", "reasoning": "aligns_with_bias"})
    MemoryMCP->>Redis: Check time_gate, whipsaw, invalidation, position rules
    Redis-->>MemoryMCP: All 4 rules PASS
    MemoryMCP-->>TradeCopilot: {"consistent": true, "recommendation": "proceed"}
    
    Note over TradeCopilot: Step 5: Store Decision
    TradeCopilot->>MemoryMCP: store_trading_decision({"symbol": "SPY", "decision_type": "position_entry", "content": {"direction": "long", "instrument": "SPY_473C"}})
    MemoryMCP->>Redis: Store position entry with full context
    Redis-->>MemoryMCP: Stored with decision_id: "dec_spy_094523"
    MemoryMCP-->>TradeCopilot: {"success": true, "decision_id": "dec_spy_094523"}
    
    TradeCopilot-->>User: "YES - BUY SPY 473C. Aligns with bullish bias (23min active). Entry aligns with VWAP support."
```

## Architectural Design / Consideration

### Whipsaws Prevention with Complete Tool Calls

```mermaid
sequenceDiagram
    participant Trader
    participant LLM
    participant Memory
    
    Note over Trader,LLM: 9:30 AM - First Analysis (No Previous Bias)
    Trader->>LLM: "Analyze SPY"
    LLM->>Memory: get_current_bias({"symbol": "SPY"})
    Memory-->>LLM: {"bias": null, "message": "No bias established"}
    Note over LLM: Fresh analysis: SPY bullish breakout
    LLM->>Memory: store_trading_decision({"symbol": "SPY", "decision_type": "bias_establishment", "content": {"bias": "bullish", "reasoning": "VWAP breakout with volume", "confidence": 85, "invalidation_level": 471.50}})
    Memory-->>LLM: {"success": true, "decision_id": "dec_spy_093000"}
    LLM-->>Trader: "BULLISH BIAS ESTABLISHED - BUY CALLS. Invalidation: 471.50"
    
    Note over Trader,LLM: 9:37 AM - Attempted Flip (7 min later)
    Trader->>LLM: "SPY looks weak now"
    LLM->>Memory: get_current_bias({"symbol": "SPY"})
    Memory-->>LLM: {"bias": "bullish", "established_at": "09:30Z", "time_held_minutes": 7}
    Note over LLM: Wants to change to bearish
    LLM->>Memory: check_consistency({"symbol": "SPY", "proposed_bias": "bearish", "reasoning": "weakness_on_pullback"})
    Memory-->>LLM: {"consistent": false, "conflicts": [{"type": "time_gate", "time_remaining": 8}], "recommendation": "block_signal"}
    LLM->>Memory: store_trading_decision({"symbol": "SPY", "decision_type": "signal_blocked", "content": {"proposed_bias": "bearish", "block_reason": "time_gate", "time_remaining_minutes": 8}})
    Memory-->>LLM: {"success": true, "decision_id": "dec_spy_093700"}
    LLM-->>Trader: "HOLD POSITION - Minor pullback normal. Bias valid for 8 more minutes or until break below 471.50"
    
    Note over Trader,LLM: Result: Prevented emotional whipsaw with audit trail
```

## Core Tools Summary
1. **get_current_bias** ✅ Retrieves established market bias and context
2. **store_trading_decision** ✅ Stores all trading decisions with full audit trail  
3. **check_consistency** ✅ Validates new signals against 4 consistency rules

**Removed:** `get_active_positions` - Position tracking handled within bias context

---
# Core Tools Input/Output Specifications

## Tool 1: `get_current_bias`

**Purpose**: Retrieve established market bias and timing context for symbol

### Input Parameters
```json
{
  "name": "get_current_bias",
  "arguments": {
    "symbol": "SPY"                    // Required: Trading symbol (e.g., SPY, QQQ, AAPL)
  }
}
```

### Output Format

#### Success Response
```json
{
  "bias": "bullish",                    // Current bias: bullish/bearish/neutral
  "established_at": "2024-01-15T09:45:00Z", // ISO timestamp when bias was set
  "confidence": 85,                     // Confidence level (1-100)
  "invalidation_level": 471.50,         // Price level that invalidates bias
  "time_held_minutes": 23,              // Minutes since bias establishment
  "reasoning": "Breaking above VWAP with volume confirmation", // Original reasoning
  "market_condition": "normal"           // Market state when established
}
```

#### No Bias Response
```json
{
  "bias": null,
  "message": "No bias established for SPY",
  "suggestion": "Establish initial bias based on market analysis"
}
```

#### Error Response
```json
{
  "error": "storage_unavailable",
  "message": "Unable to connect to memory storage",
  "fallback": "Continue without memory context"
}
```

---

## Tool 2: `store_trading_decision`

**Purpose**: Store important trading decisions with full context

```mermaid
flowchart TD
    START[store_trading_decision called] --> VALIDATE[Validate all parameters]
    VALIDATE --> |Missing Required| ERROR1[Return error: Missing fields]
    VALIDATE --> |Valid| TYPE{Decision Type?}

    TYPE --> |bias_establishment| BIAS[Process bias establishment]
    TYPE --> |position_entry| POS[Process position entry]
    TYPE --> |signal_blocked| BLOCK[Process blocked signal]
    TYPE --> |session_close| SESSION[Process session close]

    BIAS --> STORE_BIAS[Store to bias for symbol]
    POS --> STORE_POS[Store to positions for symbol]
    BLOCK --> STORE_BLOCK[Store to decisions for symbol]
    SESSION --> STORE_SESSION[Store to session for date]

    STORE_BIAS --> UPDATE_HISTORY[Update change history]
    STORE_POS --> UPDATE_HISTORY
    STORE_BLOCK --> UPDATE_HISTORY
    STORE_SESSION --> ARCHIVE[Archive session data]

    UPDATE_HISTORY --> SUCCESS[Return success]
    ARCHIVE --> SUCCESS

    ERROR1 --> END
    SUCCESS --> END

```

#### Algorithm Details:

```
FUNCTION store_trading_decision(symbol, decision_type, content):
    1. INPUT VALIDATION:
       - Validate symbol format
       - Check decision_type in allowed values
       - Validate content structure based on type
       - Return detailed error if validation fails
    
    2. DECISION TYPE ROUTING:
       
       IF decision_type == "bias_establishment":
           - Validate bias in ["bullish", "bearish", "neutral"]
           - Require invalidation_level for directional bias
           - Require confidence score (1-100)
           - Store to: "bias:{symbol}"
           
       IF decision_type == "position_entry":
           - Validate position direction
           - Store entry price and size
           - Link to current bias
           - Store to: "positions:{symbol}"
           
       IF decision_type == "signal_blocked":
           - Store block reason (time_gate, whipsaw, etc.)
           - Store original proposed signal
           - Increment block counter
           - Store to: "decisions:{symbol}"
           
       IF decision_type == "session_close":
           - Calculate session P&L
           - Store key decisions summary
           - Archive to daily storage
           - Store to: "session:{date}"
    
    3. REDIS STORAGE:
       - Use Redis transactions for consistency
       - Set appropriate TTL for each data type
       - Handle storage failures with retries
    
    4. HISTORY TRACKING:
       - Add entry to "changes:{symbol}" list
       - Maintain last N decisions for consistency checking
       - Trim old entries based on configured limits
    
    5. CROSS-REFERENCE UPDATES:
       - Update related keys (bias affects positions)
       - Maintain data consistency across keys
       - Handle partial failure scenarios
    
    RETURN {
        "success": true,
        "stored_at": "timestamp",
        "decision_id": "unique_id",
        "expires_at": "timestamp"
    }
```

### Input Examples by Decision Type

#### Bias Establishment
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "bias_establishment",
    "content": {
      "bias": "bullish",
      "reasoning": "Breaking above VWAP resistance at 472.50 with 2x average volume, RSI showing momentum but not overbought",
      "confidence": 85,
      "invalidation_level": 471.20,
      "key_levels": {
        "support": 471.20,
        "resistance": 474.50
      },
      "market_condition": "normal"
    }
  }
}
```

#### Signal Blocked
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "signal_blocked",
    "content": {
      "proposed_bias": "bearish",
      "proposed_reasoning": "Minor pullback from highs",
      "block_reason": "time_gate",
      "block_details": {
        "time_remaining_minutes": 8,
        "current_bias": "bullish",
        "current_price": 472.40,
        "invalidation_level": 471.20
      }
    }
  }
}
```

#### Position Entry
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "position_entry",
    "content": {
      "direction": "long",
      "instrument": "SPY_473C_20240119",
      "entry_price": 1.25,
      "size": 5,
      "reasoning": "Aligns with bullish bias, entry at VWAP support",
      "linked_bias": "bullish"
    }
  }
}
```

### Output Format

#### Success Response
```json
{
  "success": true,
  "stored_at": "2024-01-15T09:45:23Z",
  "decision_id": "dec_spy_20240115_094523",
  "expires_at": "2024-01-16T09:45:23Z",
  "storage_details": {
    "redis_key": "bias:SPY",
    "history_updated": true,
    "cross_references": ["current_bias", "symbol_history"]
  }
}
```

#### Error Response
```json
{
  "success": false,
  "error": "validation_failed",
  "message": "Invalid bias value: must be bullish, bearish, or neutral",
  "details": {
    "field": "content.bias",
    "provided_value": "sideways",
    "allowed_values": ["bullish", "bearish", "neutral"]
  }
}
```

---

## Tool 3: `check_consistency`


**Purpose**: Validates new signals against recent decisions to prevent contradictory trading

### Input Parameters

```json
{
  "name": "check_consistency",
  "arguments": {
    "symbol": "SPY",                    // Required: Trading symbol
    "proposed_bias": "bearish",         // Required: New bias (bullish/bearish/neutral)
    "reasoning": "failed breakdown",    // Required: Why changing bias
    "proposed_action": "sell_calls",    // Optional: Specific action
    "override_time_gate": false,        // Optional: Force override (dangerous)
    "market_condition": "choppy"        // Optional: Current market state
  }
}
```

### Output Format

```json
{
  "consistent": false,                  // Can proceed with signal?
  "conflicts": [                        // List of rule violations
    {
      "type": "time_gate",             // Rule type
      "severity": "high",              // high/medium/low
      "message": "Bias change within 15 minutes",
      "current_value": "7 minutes",
      "threshold": "15 minutes",
      "time_remaining": "8 minutes"
    }
  ],
  "recommendation": "block_signal",     // block_signal/proceed/caution
  "guidance": "Wait 8 minutes before bias change",
  "context": {
    "current_bias": "bullish",
    "established_at": "2024-01-15T09:30:00Z",
    "time_held": "7 minutes",
    "confidence": 85,
    "invalidation_level": 471.50,
    "recent_changes": 1
  },
  "debug_info": {                       // For troubleshooting
    "rules_checked": ["time_gate", "whipsaw", "invalidation", "position"],
    "current_price": 472.60,
    "processing_time_ms": 12
  }
}
```

## High-Level Workflow

```mermaid
flowchart TD
    START[User Query: SPY looks weak] --> TC[Trade Copilot Analysis]
    
    TC --> ANALYZE[AI Analyzes Market Data]
    ANALYZE --> CONCLUDE[AI Concludes: BEARISH]
    
    CONCLUDE --> CHECK[Call check_consistency]
    CHECK --> RULES[Apply 4 Consistency Rules]
    
    RULES --> RULE1{Rule 1: Time Gate}
    RULE1 -->|Pass| RULE2{Rule 2: Whipsaw Check}
    RULE1 -->|Fail| BLOCK1[Block Signal]
    
    RULE2 -->|Pass| RULE3{Rule 3: Invalidation}
    RULE2 -->|Fail| BLOCK2[Block Signal]
    
    RULE3 -->|Pass| RULE4{Rule 4: Position Check}
    RULE3 -->|Fail| BLOCK3[Block Signal]
    
    RULE4 -->|Pass| ALLOW[Allow Signal Change]
    RULE4 -->|Fail| BLOCK4[Block Signal]
    
    BLOCK1 --> RESPONSE1[Return: Hold position, wait X minutes]
    BLOCK2 --> RESPONSE2[Return: Choppy market, wait for breakout]
    BLOCK3 --> RESPONSE3[Return: Still above invalidation level]
    BLOCK4 --> RESPONSE4[Return: Conflicts with open position]
    
    ALLOW --> RESPONSE5[Return: Signal change approved]
    
    RESPONSE1 --> STORE[Store Decision in Memory]
    RESPONSE2 --> STORE
    RESPONSE3 --> STORE
    RESPONSE4 --> STORE
    RESPONSE5 --> STORE
```

## Configuration Parameters

```json
{
  "consistency_rules": {
    "time_gate": {
      "enabled": true,
      "default_minutes": 15,
      "0dte_minutes": 20,
      "override_allowed": false
    },
    "whipsaw_detection": {
      "enabled": true,
      "max_changes_per_hour": 2,
      "lookback_minutes": 60,
      "choppy_market_threshold": 3
    },
    "invalidation_enforcement": {
      "enabled": true,
      "require_level_breach": true,
      "buffer_percent": 0.05
    },
    "position_protection": {
      "enabled": true,
      "allow_override": false,
      "check_open_orders": true
    }
  },
  "market_conditions": {
    "normal": {
      "time_gate_minutes": 15,
      "max_changes_hour": 2
    },
    "volatile": {
      "time_gate_minutes": 20,
      "max_changes_hour": 1
    },
    "choppy": {
      "time_gate_minutes": 25,
      "max_changes_hour": 1
    }
  }
}
```

## Complete Integration Workflow

```mermaid
sequenceDiagram
    participant User
    participant TradeBot as Trade Copilot
    participant MD as Market Data MCP
    participant OF as Order Flow MCP
    participant TM as Trading Memory MCP
    participant Redis
    
    User->>TradeBot: "SPY looking weak, should I sell?"
    
    Note over TradeBot: Step 1: Gather Market Intelligence
    
    TradeBot->>MD: get_market_data("SPY")
    MD-->>TradeBot: {price: 472.60, volume: 800k, rsi: 54}
    
    TradeBot->>OF: get_order_flow("SPY")
    OF-->>TradeBot: {sentiment: "slightly_bearish", volume: "light"}
    
    Note over TradeBot: Step 2: AI Analysis
    
    TradeBot->>TradeBot: Analyze data → Conclude: BEARISH
    
    Note over TradeBot: Step 3: Memory Consistency Check
    
    TradeBot->>TM: check_consistency("SPY", "bearish", "weakness_signals")
    TM->>Redis: GET bias:SPY, changes:SPY, positions:SPY
    Redis-->>TM: Current bias: bullish (7min ago)
    
    TM->>TM: Apply 4 consistency rules
    TM-->>TradeBot: {consistent: false, conflicts: ["time_gate"]}
    
    Note over TradeBot: Step 4: Store Blocked Decision
    
    TradeBot->>TM: store_trading_decision({"symbol": "SPY", "decision_type": "signal_blocked", "content": {"proposed_bias": "bearish", "block_reason": "time_gate", "time_remaining": 8}})
    TM->>Redis: Store blocked signal with full context
    
    TradeBot-->>User: "HOLD - Minor weakness normal. Bullish bias active (7min). Wait 8 more minutes or break below 471.50"
```



## Real-World Example Flow

```mermaid
sequenceDiagram
    participant User
    participant TradeBot
    participant Memory
    participant ConsistencyEngine
    
    Note over User,ConsistencyEngine: 9:30 AM - Initial Trade
    
    User->>TradeBot: "Analyze SPY"
    TradeBot->>Memory: get_current_bias("SPY")
    Memory-->>TradeBot: None
    TradeBot->>Memory: store_trading_decision(BULLISH)
    TradeBot-->>User: "BUY SPY 473 Calls"
    
    Note over User,ConsistencyEngine: 9:37 AM - Attempted Flip (7 min later)
    
    User->>TradeBot: "SPY pulling back"
    TradeBot->>ConsistencyEngine: check_consistency("SPY", "bearish")
    ConsistencyEngine->>Memory: Get bias timestamp
    Memory-->>ConsistencyEngine: "9:30 AM (7 min ago)"
    ConsistencyEngine-->>TradeBot: BLOCKED - Time gate (wait 8 min)
    TradeBot-->>User: "Hold position - minor pullback normal"
    
    Note over User,ConsistencyEngine: 10:15 AM - Valid Change (45 min later)
    
    User->>TradeBot: "SPY broke support"
    TradeBot->>ConsistencyEngine: check_consistency("SPY", "bearish")
    ConsistencyEngine->>Memory: Check all rules
    Memory-->>ConsistencyEngine: Time OK, No whipsaw, Level breached
    ConsistencyEngine-->>TradeBot: ALLOWED - All rules pass
    TradeBot-->>User: "EXIT calls, Consider puts"
```

## What Gets Stored in Memory

```mermaid
graph LR
    subgraph "Redis Memory Storage"
        B1[bias:SPY]
        B1 --> B1D["{'bias': 'bullish',<br/>'established_at': '09:30',<br/>'confidence': 85,<br/>'invalidation': 471.50}"]
        
        C1[changes:SPY]
        C1 --> C1D["[<br/>{'time': '09:30', 'to': 'bullish'},<br/>{'time': '10:15', 'to': 'bearish'}<br/>]"]
        
        D1[decisions:SPY]
        D1 --> D1D["[<br/>{'type': 'bias_establishment', 'blocked': false},<br/>{'type': 'signal_blocked', 'reason': 'time_gate'}<br/>]"]
    end
```

---

## Complete First Call and Follow-up Examples

### Example 1: Morning Bias Establishment (First Call)

### User Input
**User:** *"What's SPY looking like this morning?"*

### LLM Tool Call Sequence

1. **Check for existing bias:**
```json
{
  "name": "get_current_bias",
  "arguments": {
    "symbol": "SPY"
  }
}
```
**Response:**
```json
{
  "bias": null,
  "message": "No bias established for SPY",
  "suggestion": "Establish initial bias based on market analysis"
}
```

2. **LLM gets market data and concludes bullish, then stores decision:**
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "bias_establishment",
    "content": {
      "bias": "bullish",
      "reasoning": "Gap up above previous high 471.90, holding above VWAP with 1.5x average volume in first 30min",
      "confidence": 80,
      "invalidation_level": 471.20,
      "market_condition": "normal"
    }
  }
}
```
**Response:**
```json
{
  "success": true,
  "stored_at": "2024-01-15T09:30:15Z",
  "decision_id": "dec_spy_20240115_093015",
  "expires_at": "2024-01-16T09:30:15Z"
}
```

### User Response
**LLM:** *"SPY BULLISH BIAS ESTABLISHED - Gap up above yesterday's high with strong volume. Current: 472.80, above VWAP support. Invalidation level: 471.20. Consider SPY calls on any VWAP retest."*

---

### Example 2: Follow-up Call - Signal Blocked (7 minutes later)

### User Input
**User:** *"SPY is pulling back, should I exit?"*

### LLM Tool Call Sequence

1. **Check current bias:**
```json
{
  "name": "get_current_bias",
  "arguments": {
    "symbol": "SPY"
  }
}
```
**Response:**
```json
{
  "bias": "bullish",
  "established_at": "2024-01-15T09:30:15Z",
  "confidence": 80,
  "invalidation_level": 471.20,
  "time_held_minutes": 7,
  "reasoning": "Gap up above previous high 471.90, holding above VWAP with 1.5x average volume",
  "market_condition": "normal"
}
```

2. **LLM sees minor pullback, wants to check if bearish change is valid:**
```json
{
  "name": "check_consistency",
  "arguments": {
    "symbol": "SPY",
    "proposed_bias": "bearish",
    "reasoning": "Minor pullback from morning highs",
    "proposed_action": "exit_position"
  }
}
```
**Response:**
```json
{
  "consistent": false,
  "conflicts": [
    {
      "type": "time_gate",
      "severity": "high",
      "message": "Bias change within 15 minutes of establishment",
      "time_remaining": "8 minutes",
      "current_value": "7 minutes",
      "threshold": "15 minutes"
    }
  ],
  "recommendation": "block_signal",
  "guidance": "Wait 8 minutes before bias change or until price breaks below 471.20",
  "context": {
    "current_bias": "bullish",
    "established_at": "2024-01-15T09:30:15Z",
    "time_held": "7 minutes",
    "confidence": 80,
    "invalidation_level": 471.20,
    "recent_changes": 0
  }
}
```

3. **LLM stores the blocked signal:**
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "signal_blocked",
    "content": {
      "proposed_bias": "bearish",
      "proposed_reasoning": "Minor pullback from morning highs",
      "block_reason": "time_gate",
      "block_details": {
        "time_remaining_minutes": 8,
        "current_bias": "bullish",
        "current_price": 472.40,
        "invalidation_level": 471.20
      }
    }
  }
}
```
**Response:**
```json
{
  "success": true,
  "stored_at": "2024-01-15T09:37:23Z",
  "decision_id": "dec_spy_20240115_093723"
}
```

### User Response
**LLM:** *"HOLD POSITION - Minor pullback is normal in bullish setup. Bias established only 7 minutes ago. Wait 8 more minutes or exit only if break below invalidation level 471.20. Current: 472.40 (still valid)."*

---

### Example 3: Valid Follow-up Call - Change Allowed (45 minutes later)

### User Input
**User:** *"SPY broke below support, what now?"*

### LLM Tool Call Sequence

1. **Check current bias:**
```json
{
  "name": "get_current_bias",
  "arguments": {
    "symbol": "SPY"
  }
}
```
**Response:**
```json
{
  "bias": "bullish",
  "established_at": "2024-01-15T09:30:15Z",
  "confidence": 80,
  "invalidation_level": 471.20,
  "time_held_minutes": 45,
  "reasoning": "Gap up above previous high with strong volume",
  "market_condition": "normal"
}
```

2. **LLM sees price at 471.10 (below invalidation), wants to change to bearish:**
```json
{
  "name": "check_consistency",
  "arguments": {
    "symbol": "SPY",
    "proposed_bias": "bearish",
    "reasoning": "Broke below invalidation level 471.20, now at 471.10",
    "proposed_action": "exit_longs_consider_puts"
  }
}
```
**Response:**
```json
{
  "consistent": true,
  "conflicts": [],
  "recommendation": "proceed",
  "guidance": "Signal change approved - invalidation level breached",
  "context": {
    "current_bias": "bullish",
    "established_at": "2024-01-15T09:30:15Z",
    "time_held": "45 minutes",
    "confidence": 80,
    "invalidation_level": 471.20,
    "current_price": 471.10,
    "level_breached": true
  }
}
```

3. **LLM stores the new bearish bias:**
```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "bias_establishment",
    "content": {
      "bias": "bearish",
      "reasoning": "Failed to hold above 471.20 invalidation level, now showing weakness below key support",
      "confidence": 75,
      "invalidation_level": 472.50,
      "market_condition": "normal"
    }
  }
}
```
**Response:**
```json
{
  "success": true,
  "stored_at": "2024-01-15T10:15:30Z",
  "decision_id": "dec_spy_20240115_101530"
}
```

### User Response
**LLM:** *"BIAS CHANGE TO BEARISH - SPY broke below invalidation level 471.20, now at 471.10. Previous bullish thesis invalidated after 45 minutes. EXIT long positions. New invalidation: 472.50. Consider SPY puts on any bounce to VWAP."*

---
