# MCP Trading Memory

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-1.0.0-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> ⚠️ **Note:** This project is actively under development and subject to change. APIs and architecture may evolve as testing and feature integration progress. I'll make the code repo public after additional testing. 

**Trading memory system for AI assistants via Model Context Protocol (MCP)**

Persistent memory capabilities designed for trade-copilot integration. Prevents contradictory signals, maintains trading context, and enforces consistency across trading sessions.

## Architecture Overview

```mermaid
graph TB
    subgraph "Trade Copilot Integration"
        TC[Trade Copilot Main]
        LLM[LLM Service]
        MCP[MCP Client]
    end
    
    subgraph "Memory MCP Server"
        MT[Memory Tools]
        CE[Consistency Engine]
        MS[Memory Storage]
    end
    
    subgraph "Existing MCP Servers"
        MD[Market Data]
        OF[Order Flow]
        OPT[Options Flow]
    end
    
    TC --> LLM
    LLM --> MCP
    MCP --> MT
    MCP --> MD
    MCP --> OF
    MCP --> OPT
    MT --> CE
    MT --> MS
```


### Trade Copilot Integration

Add to `trade-copilot/mcp_servers.json`:

```json
{
  "mcpServers": {
    "trading-memory": {
      "command": "mcp-trading-memory",
      "args": [],
      "env": {
        "MEMORY_BACKEND": "redis",
        "REDIS_URL": "redis://localhost:6379",
        "BIAS_CHANGE_GATE_MINUTES": "15",
        "SESSION_MEMORY_TTL": "86400"
      }
    },
    "market-data": {
      "command": "mcp-market-data-server"
    },
    "order-flow": {
      "command": "mcp-order-flow-server"
    }
  }
}
```

## Memory Tools

### Core Memory Operations

#### `get_current_bias`
Retrieves established market bias and timing context for symbol

```json
{
  "name": "get_current_bias",
  "arguments": {
    "symbol": "SPY"
  }
}
```

**Returns:**
```json
{
  "bias": "bullish",
  "established_at": "2024-01-15T09:45:00Z",
  "confidence": 85,
  "invalidation_level": 471.50,
  "time_held_minutes": 23,
  "reasoning": "Breaking above VWAP with volume confirmation"
}
```

#### `store_trading_decision`
Stores important trading decisions with context

```json
{
  "name": "store_trading_decision",
  "arguments": {
    "symbol": "SPY",
    "decision_type": "bias_establishment",
    "content": {
      "bias": "bullish",
      "reasoning": "Breaking above VWAP with volume",
      "confidence": 85,
      "invalidation_level": 471.50,
      "key_levels": {
        "support": 470.25,
        "resistance": 473.80
      }
    }
  }
}
```

#### `check_consistency`
Validates new signals against recent decisions

```json
{
  "name": "check_consistency",
  "arguments": {
    "symbol": "SPY",
    "proposed_bias": "bearish",
    "reasoning": "Failed breakdown attempt",
    "proposed_action": "sell_calls"
  }
}
```

**Returns:**
```json
{
  "consistent": false,
  "conflicts": [
    {
      "type": "time_gate",
      "message": "Bias change within 15 minutes of establishment",
      "last_change": "2024-01-15T09:45:00Z"
    },
    {
      "type": "position_conflict", 
      "message": "Contradicts existing bullish position",
      "current_position": "long_calls_473"
    }
  ],
  "recommendation": "wait_or_justify"
}
```

#### `get_active_positions`
Retrieves current positions with entry context

```json
{
  "name": "get_active_positions",
  "arguments": {
    "symbol": "SPY"
  }
}
```

#### `get_pattern_memory`
Searches historical patterns and outcomes

```json
{
  "name": "get_pattern_memory",
  "arguments": {
    "setup_type": "vwap_breakout",
    "market_condition": "low_volatility",
    "time_of_day": "morning",
    "limit": 5
  }
}
```

#### `update_position`
Updates position status and reasoning

```json
{
  "name": "update_position",
  "arguments": {
    "symbol": "SPY",
    "position_id": "pos_001",
    "status": "active",
    "current_pnl": 150.50,
    "notes": "Target hit, trailing stop"
  }
}
```

## Trading Workflow Scenarios

### Scenario 1: Morning Bias Establishment

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    participant MD as Market Data
    
    TC->>LLM: "Analyze SPY for morning setup"
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: No bias established
    
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Current price, volume, indicators
    
    Note over LLM: Analyzes fresh data
    
    LLM->>TM: store_trading_decision(bias_establishment)
    TM-->>LLM: Stored successfully
    
    LLM-->>TC: "Establishing bullish bias at 472.80"
```

### Scenario 2: Position Entry with Memory Check

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service  
    participant TM as Trading Memory
    participant OF as Order Flow
    
    TC->>LLM: "Should I enter SPY calls?"
    
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias established 9:45 AM
    
    LLM->>TM: get_active_positions("SPY") 
    TM-->>LLM: No current positions
    
    LLM->>OF: get_order_flow("SPY")
    OF-->>LLM: Strong call buying, bullish flow
    
    LLM->>TM: check_consistency(proposed_action: "buy_calls")
    TM-->>LLM: Consistent with established bias
    
    LLM->>TM: store_trading_decision(position_entry)
    TM-->>LLM: Position stored
    
    LLM-->>TC: "Entry signal: SPY 473C, aligns with bias"
```

### Scenario 3: Conflicting Signal Prevention

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    participant MD as Market Data
    
    TC->>LLM: "SPY looking weak, should I sell?"
    
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias (10 min ago), confidence 85%
    
    LLM->>TM: get_active_positions("SPY")
    TM-->>LLM: Long SPY 473C, entry 1.25
    
    LLM->>MD: get_current_price("SPY")
    MD-->>LLM: 472.50 (slight pullback)
    
    LLM->>TM: check_consistency(proposed_bias: "bearish")
    TM-->>LLM: CONFLICT: Time gate active, position conflict
    
    Note over LLM: Consistency check failed
    
    LLM-->>TC: "Minor pullback, maintaining bullish bias. Invalidation at 471.50"
```

### Scenario 4: Pattern Recognition Workflow

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    participant MD as Market Data
    
    TC->>LLM: "Is this VWAP bounce tradeable?"
    
    LLM->>MD: get_market_structure("SPY")
    MD-->>LLM: At VWAP, volume increasing
    
    LLM->>TM: get_pattern_memory(setup_type: "vwap_bounce")
    TM-->>LLM: Historical data: 68% win rate, 3 similar setups
    
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias active
    
    LLM->>TM: check_consistency(proposed_action: "add_position")
    TM-->>LLM: Consistent with bias and patterns
    
    LLM-->>TC: "VWAP bounce setup: 68% historical win rate, add small position"
```

### Scenario 5: Real-time Status Check ("Check Now")

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    participant MD as Market Data
    participant OF as Order Flow
    
    TC->>LLM: "Check now - what does SPY look like?"
    
    Note over LLM: Comprehensive status check
    
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias since 9:45 AM, confidence 85%
    
    LLM->>TM: get_active_positions("SPY")
    TM-->>LLM: Long SPY 473C x5, entry 1.25, current +$75
    
    LLM->>MD: get_current_price("SPY")
    MD-->>LLM: 472.95, near VWAP, moderate volume
    
    LLM->>OF: get_order_flow("SPY")
    OF-->>LLM: Mixed flow, slight call bias
    
    LLM->>TM: get_pattern_memory(current_setup)
    TM-->>LLM: Similar setups: 72% win rate
    
    Note over LLM: Synthesizes all context
    
    LLM-->>TC: "SPY Status: Maintaining bullish bias (25min), position +$75, holding above VWAP. Pattern confidence remains high."
```

### Scenario 6: Contradictory Signals Problem & Solution

#### Part A: WITHOUT Memory (Contradictory Signals)

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service (No Memory)
    participant MD as Market Data
    
    Note over TC,MD: 9:45 AM - First Analysis
    
    TC->>LLM: "Analyze SPY"
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.80, above VWAP, strong volume
    LLM-->>TC: "🟢 BULLISH: Buy SPY 473 calls"
    
    Note over TC,MD: 9:52 AM - Second Analysis (7 mins later)
    
    TC->>LLM: "How's SPY looking?"
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.60, slight pullback, volume decreasing
    LLM-->>TC: "🔴 BEARISH: Consider SPY puts, momentum fading"
    
    Note over TC,MD: 9:58 AM - Third Analysis (6 mins later)
    
    TC->>LLM: "SPY update please"
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.75, back near VWAP
    LLM-->>TC: "🟢 BULLISH: Good entry for calls again"
    
    Note over TC,MD: Result: 3 contradictory signals in 13 minutes!
```

#### Part B: WITH Memory (Consistent Analysis)

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service (With Memory)
    participant TM as Trading Memory
    participant MD as Market Data
    
    Note over TC,MD: 9:45 AM - First Analysis
    
    TC->>LLM: "Analyze SPY"
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: No bias established
    
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.80, above VWAP, strong volume
    
    LLM->>TM: store_trading_decision(bias_establishment)
    TM-->>LLM: Bullish bias stored
    
    LLM-->>TC: "BULLISH BIAS ESTABLISHED: Buy SPY 473 calls. Invalidation: 471.50"
    
    Note over TC,MD: 9:52 AM - Second Analysis (7 mins later)
    
    TC->>LLM: "How's SPY looking?"
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias (7 min ago), confidence 85%
    
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.60, slight pullback, volume decreasing
    
    LLM->>TM: check_consistency(proposed_bias: "bearish")
    TM-->>LLM: CONFLICT: Time gate active (< 15 min)
    
    Note over LLM: Memory prevents flip-flopping
    
    LLM-->>TC: "MAINTAINING BULLISH BIAS: Minor pullback normal. Still above invalidation (471.50)"
    
    Note over TC,MD: 9:58 AM - Third Analysis (6 mins later)
    
    TC->>LLM: "SPY update please"
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias (13 min ago), confidence 85%
    
    LLM->>MD: get_market_data("SPY")
    MD-->>LLM: Price 472.75, back near VWAP
    
    Note over LLM: Consistent with established bias
    
    LLM-->>TC: "BIAS CONFIRMED: Back to entry levels, bullish thesis intact"
    
    Note over TC,MD: Result: Consistent bias maintained, no whipsaws!
```

### Scenario 7: Memory-Based Contradiction Detection

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    participant MD as Market Data
    
    Note over TC,MD: Setup: Established bullish bias + long position
    
    TC->>LLM: "SPY breaking down, should I panic sell?"
    
    LLM->>TM: get_current_bias("SPY")
    TM-->>LLM: Bullish bias established 20 min ago
    
    LLM->>TM: get_active_positions("SPY")
    TM-->>LLM: Long 5x SPY 473C, entry 1.25, reasoning: "VWAP breakout"
    
    LLM->>MD: get_current_price("SPY")
    MD-->>LLM: 471.80 (below entry but above invalidation)
    
    LLM->>TM: check_consistency(panic_sell, breaking_down)
    
    TM-->>LLM: CONFLICT: Position conflict + Above invalidation
    
    Note over LLM: Memory prevents panic decision
    
    LLM-->>TC: "HOLD POSITION: Still above invalidation (471.50). Normal pullback in bullish setup. Stick to plan."
```

### Scenario 8: End of Session Memory Update

```mermaid
sequenceDiagram
    participant TC as Trade Copilot
    participant LLM as LLM Service
    participant TM as Trading Memory
    
    TC->>LLM: "Market closing, update session"
    
    LLM->>TM: get_active_positions("all")
    TM-->>LLM: SPY position: +$285 profit
    
    LLM->>TM: store_trading_decision(session_close)
    Note over TM: Stores outcome data
    
    LLM->>TM: store_pattern_outcome(vwap_breakout, profitable, 150min, 22.8%)
    
    TM-->>LLM: Pattern and session stored
    
    LLM-->>TC: "Session profitable: +$285, pattern success recorded"
```

## Contradictory Signals Problem Analysis

### The Problem: AI Memory Loss
Without persistent memory, AI trading assistants suffer from "conversational amnesia" - each query is analyzed in isolation, leading to contradictory recommendations within minutes.

```mermaid
graph TD
    subgraph "Without Memory (Broken)"
        Q1[Query 1: Analyze SPY] --> A1[Fresh Analysis Only]
        A1 --> R1[BULLISH: Buy calls]
        
        Q2[Query 2: SPY update 7min later] --> A2[Fresh Analysis Only]
        A2 --> R2[BEARISH: Buy puts]
        
        Q3[Query 3: How SPY 6min later] --> A3[Fresh Analysis Only]  
        A3 --> R3[BULLISH: Buy calls again]
    end
    
    subgraph "Result"
        PROB[3 contradictory signals<br/>13 minutes<br/>Unusable for trading]
    end
    
    R1 --> PROB
    R2 --> PROB
    R3 --> PROB
```

### The Solution: Memory-Driven Consistency

```mermaid
graph TD
    subgraph "With Memory (Consistent)"
        Q1[Query 1: Analyze SPY] --> M1[Check Memory + Fresh Data]
        M1 --> R1[BULLISH BIAS ESTABLISHED]
        R1 --> S1[Store bias + invalidation level]
        
        Q2[Query 2: SPY update 7min later] --> M2[Memory: Bullish bias active<br/>Fresh: Minor pullback]
        M2 --> C1[Consistency Check: CONFLICT]
        C1 --> R2[MAINTAINING BIAS: Minor pullback normal]
        
        Q3[Query 3: How SPY 6min later] --> M3[Memory: Bullish bias<br/>Fresh: Back to levels]
        M3 --> C2[Consistency Check: ALIGNED]
        C2 --> R3[BIAS CONFIRMED: Thesis intact]
    end
    
    subgraph "Result"
        SOL[Consistent analysis<br/>Professional discipline<br/>Tradeable signals]
    end
    
    R1 --> SOL
    R2 --> SOL
    R3 --> SOL
```

### Memory Tools That Solve This

| Problem | Memory Tool | How It Helps |
|---------|-------------|--------------|
| **Bias Flip-Flopping** | `get_current_bias` + `check_consistency` | Maintains established bias, prevents rapid changes |
| **Position Conflicts** | `get_active_positions` + position validation | Prevents recommendations that contradict holdings |
| **Panic Decisions** | Time gates + invalidation levels | Enforces professional discipline and exit rules |
| **Context Loss** | `get_pattern_memory` | Provides historical context for current setup |
| **Status Confusion** | Real-time status synthesis | Combines memory + fresh data for complete picture |


## Tool Integration Patterns

### Pre-Decision Memory Check
```mermaid
flowchart TD
    START[Trading Decision Request] --> CHECK[Check Current Context]
    CHECK --> |get_current_bias| BIAS[Retrieve Established Bias]
    CHECK --> |get_active_positions| POS[Check Current Positions]
    CHECK --> |get_pattern_memory| PAT[Find Similar Patterns]
    
    BIAS --> ANALYZE[Analyze with Context]
    POS --> ANALYZE
    PAT --> ANALYZE
    
    ANALYZE --> VALIDATE[check_consistency]
    VALIDATE --> |Pass| EXECUTE[Execute Decision]
    VALIDATE --> |Fail| WARN[Warning/Block]
    
    EXECUTE --> STORE[store_trading_decision]
    WARN --> JUSTIFY[Require Justification]
    JUSTIFY --> |Override| STORE
    JUSTIFY --> |Cancel| END[Cancel Action]
    
    STORE --> END
```

### Memory Update Flow
```mermaid
flowchart TD
    DECISION[Trading Decision Made] --> TYPE{Decision Type}
    
    TYPE -->|Bias Change| UB[Update Bias Memory]
    TYPE -->|Position Entry| UP[Update Position Memory]  
    TYPE -->|Pattern Complete| UPT[Update Pattern Memory]
    TYPE -->|Session Event| US[Update Session Memory]
    
    UB --> VALIDATE[Validate Consistency]
    UP --> VALIDATE
    UPT --> CLEAN[Cleanup Old Data]
    US --> SUMMARIZE[Summarize if Needed]
    
    VALIDATE --> |Pass| COMMIT[Commit to Storage]
    VALIDATE --> |Fail| REJECT[Reject Update]
    
    CLEAN --> COMMIT
    SUMMARIZE --> COMMIT
    
    COMMIT --> NOTIFY[Notify Success]
    REJECT --> ERROR[Return Error]
```

## Configuration

### Environment Variables
```bash
# Storage Backend
MEMORY_BACKEND=redis
REDIS_URL=redis://localhost:6379/0

# Consistency Rules
BIAS_CHANGE_GATE_MINUTES=15
MAX_CONTRADICTIONS_HOUR=2
POSITION_CONSISTENCY_CHECK=true

# Memory Management  
SESSION_MEMORY_TTL=86400
PATTERN_MEMORY_TTL=2592000
CONVERSATION_MEMORY_LIMIT=50

# Trading Rules
MAX_POSITION_SIZE=10000
RISK_LIMIT_PERCENT=2.0
TIME_STOP_MINUTES=240
```



## Memory Lifecycle

### Session Lifecycle
```mermaid
timeline
    title Trading Session Memory Lifecycle
    
    section Pre-Market
        Memory Init : Load previous session context
                   : Initialize daily memory structures
                   : Set session parameters
    
    section Market Open
        Bias Establishment : Store initial market bias
                          : Set key levels and invalidation
                          : Initialize position tracking
    
    section Active Trading
        Decision Tracking : Store each trading decision
                         : Update position status
                         : Validate consistency
                         : Pattern matching
    
    section Session Close
        Session Summary : Summarize key decisions
                       : Store successful patterns
                       : Archive session data
                       : Cleanup temporary data
    
    section Post-Session
        Pattern Analysis : Update pattern success rates
                        : Merge similar setups
                        : Optimize memory structure
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Disclaimer

This software is for educational and research purposes. Trading involves risk of loss.
