# ADR-001: NIFTY 50 Double Confirmation BUY & SELL Strategy

**Status:** Accepted  
**Date:** January 2026  
**Author:** Trading System Team  
**Deciders:** Strategy Development Team

---

## Context

We need an automated trading strategy for NIFTY 50 index that:
- Minimizes false signals through multi-timeframe confirmation
- Uses proven technical indicators for trend identification
- Supports both LONG (BUY) and SHORT (SELL) positions
- Implements indicator-based exit (no fixed SL/Target)
- Can operate in both simulation and live trading modes
- Integrates with Zerodha Kite Connect API

---

## Decision

We will implement a **Double Confirmation Strategy** for both BUY and SELL that requires alignment of technical indicators on **two separate timeframes** (5-minute and 2-minute) before executing trades.

---

## Strategy Architecture

### 1. Multi-Timeframe Approach

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                    DOUBLE CONFIRMATION SYSTEM (BUY & SELL)                     │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│   PRIMARY TIMEFRAME (5-minute)          CONFIRMATION TIMEFRAME (2-min)        │
│   ┌─────────────────────────┐           ┌─────────────────────────┐           │
│   │  Check every 10 seconds │           │  Check every 5 seconds  │           │
│   │                         │           │                         │           │
│   │  • SuperTrend (7,3)     │           │  • SuperTrend (7,3)     │           │
│   │  • EMA Low/High (8, 9)  │           │  • EMA Low/High (8, 9)  │           │
│   │  • EMA Crossover (8,9)  │           │  • EMA Crossover (8,9)  │           │
│   │  • StochasticRSI        │           │  • StochasticRSI        │           │
│   │  • RSI (14)             │           │  • RSI (14)             │           │
│   │  • MACD (5,13,6)        │           │  • MACD (5,13,6)        │           │
│   └───────────┬─────────────┘           └───────────┬─────────────┘           │
│               │                                      │                         │
│               └──────────────┬───────────────────────┘                         │
│                              │                                                 │
│                              ▼                                                 │
│               ┌──────────────────────────────┐                                │
│               │    BOTH TIMEFRAMES AGREE?     │                                │
│               └──────────────┬───────────────┘                                │
│                              │                                                 │
│               ┌──────────────┴──────────────┐                                 │
│               │                             │                                  │
│               ▼                             ▼                                  │
│   ┌─────────────────────┐       ┌─────────────────────┐                       │
│   │  ALL BULLISH? 🟢    │       │  ALL BEARISH? 🔴    │                       │
│   │                     │       │                     │                       │
│   │  → PLACE BUY ORDER  │       │  → PLACE SELL ORDER │                       │
│   │    (Go LONG)        │       │    (Go SHORT)       │                       │
│   │                     │       │                     │                       │
│   │  Exit: When ANY     │       │  Exit: When ANY     │                       │
│   │  indicator turns 🔴 │       │  indicator turns 🟢 │                       │
│   └─────────────────────┘       └─────────────────────┘                       │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 2. Technical Indicators

| Indicator | Parameters | Purpose | BUY Condition 🟢 | SELL Condition 🔴 |
|-----------|------------|---------|------------------|-------------------|
| **SuperTrend** | Period: 7, Multiplier: 3 | Primary trend | Direction = 1 (Bullish) | Direction = -1 (Bearish) |
| **EMA on Low/High** | Period: 8, Offset: 9 | Support/Resistance | Price > EMA Low, Rising 📈 | Price < EMA High, Falling 📉 |
| **EMA Crossover** | Fast: 8, Slow: 9 | Momentum | EMA 8 > EMA 9 🟢 | EMA 8 < EMA 9 🔴 |
| **Stochastic RSI** | RSI: 14, Stoch: 14, K: 3, D: 3 | Oversold/Overbought | < 50 or Rising | > 50 or Falling |
| **RSI** | Period: 14 | Momentum filter | < 65 and Rising | > 35 and Falling |
| **MACD** | Fast: 5, Slow: 13, Signal: 6 | Momentum | Histogram > 0 or Improving | Histogram < 0 or Declining |

### 3. Signal Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           SIGNAL GENERATION FLOW                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌───────────┐ │
│  │ Fetch 5-min │───▶│  Calculate  │───▶│   Check     │───▶│  PRIMARY  │ │
│  │    Data     │    │  Indicators │    │  Conditions │    │  SIGNAL   │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────┬─────┘ │
│                                                                  │       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────▼─────┐ │
│  │ Fetch 2-min │───▶│  Calculate  │───▶│   Check     │───▶│  CONFIRM  │ │
│  │    Data     │    │  Indicators │    │  Conditions │    │  SIGNAL   │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────┬─────┘ │
│                                                                  │       │
│                                                          ┌───────▼──────┐│
│                                                          │ PRIMARY AND  ││
│                                                          │   CONFIRM?   ││
│                                                          └───────┬──────┘│
│                                          ┌───────────────────────┴───┐   │
│                                          │                           │   │
│                                     ┌────▼────┐               ┌──────▼──┐│
│                                     │   YES   │               │   NO    ││
│                                     │ BUY NOW │               │  WAIT   ││
│                                     └─────────┘               └─────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

## BUY Conditions (LONG) - All Must Be True 🟢

### Primary Conditions (5-minute)
```python
buy_conditions_met = (
    supertrend_direction == 1           # SuperTrend Bullish 🟢
    AND close > supertrend_value        # Price above SuperTrend
    AND close > ema_low_8               # Price above EMA Low
    AND ema_8 > ema_9                   # EMA Bullish crossover 🟢
    AND (stoch_rsi_k < 50 OR rising)    # StochRSI good for buy
    AND (rsi_14 < 65 AND rising)        # RSI not overbought, rising
    AND (macd_hist > 0 OR improving)    # MACD positive momentum
)
```

### Confirmation Conditions (2-minute)
Same indicators must confirm on the shorter timeframe.

### Strong BUY Signal Override
```python
crossover_signal = supertrend_crossover OR ema_crossover
is_buy = buy_conditions_met OR (crossover_signal AND supertrend_bullish AND ema_bullish)
```

---

## SELL Conditions (SHORT) - All Must Be True 🔴

### Primary Conditions (5-minute) - OPPOSITE OF BUY
```python
sell_conditions_met = (
    supertrend_direction == -1          # SuperTrend Bearish 🔴
    AND close < supertrend_value        # Price below SuperTrend
    AND close < ema_high_8              # Price below EMA High
    AND ema_8 < ema_9                   # EMA Bearish crossover 🔴
    AND (stoch_rsi_k > 50 OR falling)   # StochRSI good for sell
    AND (rsi_14 > 35 AND falling)       # RSI not oversold, falling
    AND (macd_hist < 0 OR declining)    # MACD negative momentum
)
```

### Confirmation Conditions (2-minute)
Same BEARISH indicators must confirm on the shorter timeframe.

### Strong SELL Signal Override
```python
crossover_signal = supertrend_crossover_down OR ema_crossover_down
is_sell = sell_conditions_met OR (crossover_signal AND supertrend_bearish AND ema_bearish)
```

### BUY vs SELL Comparison Table

| Indicator | BUY (LONG) 🟢 | SELL (SHORT) 🔴 |
|-----------|---------------|-----------------|
| SuperTrend | Direction = 1 (Bullish) | Direction = -1 (Bearish) |
| Price vs ST | Price > SuperTrend | Price < SuperTrend |
| EMA Reference | EMA on LOW (support) | EMA on HIGH (resistance) |
| Price vs EMA | Price > EMA Low 📈 | Price < EMA High 📉 |
| EMA Crossover | EMA 8 > EMA 9 🟢 | EMA 8 < EMA 9 🔴 |
| StochRSI | < 50 OR Rising | > 50 OR Falling |
| RSI | < 65 AND Rising | > 35 AND Falling |
| MACD Histogram | > 0 OR Improving | < 0 OR Declining |

---

## Exit Conditions (Position Management)

### Exit Strategy: Indicator-Based Exit (No Fixed SL/Target)

**Key Principle:** Exit when ANY 2-minute indicator condition fails.

---

### EXIT LONG Position (Close BUY) 🟢➡️⬜

| Indicator | HOLD LONG | EXIT LONG (Close Buy) |
|-----------|-----------|----------------------|
| **SuperTrend** | 🟢 Bullish | Turns 🔴 Bearish |
| **EMA Low (8)** | 📈 Rising | Turns 📉 Falling |
| **EMA Crossover** | 🟢 EMA 8 > EMA 9 | Turns 🔴 EMA 8 < EMA 9 |

```python
# EXIT LONG if ANY condition fails on 2-min
exit_long = (
    supertrend_direction == -1 OR      # ST turned bearish 🔴
    ema_low_8 < prev_ema_low_8 OR      # EMA Low falling 📉
    ema_8 < ema_9                       # EMA crossed down 🔴
)
```

---

### EXIT SHORT Position (Close SELL) 🔴➡️⬜

| Indicator | HOLD SHORT | EXIT SHORT (Close Sell) |
|-----------|------------|------------------------|
| **SuperTrend** | 🔴 Bearish | Turns 🟢 Bullish |
| **EMA High (8)** | 📉 Falling | Turns 📈 Rising |
| **EMA Crossover** | 🔴 EMA 8 < EMA 9 | Turns 🟢 EMA 8 > EMA 9 |

```python
# EXIT SHORT if ANY condition fails on 2-min
exit_short = (
    supertrend_direction == 1 OR       # ST turned bullish 🟢
    ema_high_8 > prev_ema_high_8 OR    # EMA High rising 📈
    ema_8 > ema_9                       # EMA crossed up 🟢
)
```

---

### Exit Flow Diagram (Both Directions)
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    2-MIN EXIT MONITORING (Every 5 seconds)                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────────────────────────────┐    ┌─────────────────────────────────┐ │
│   │      EXIT LONG POSITION 🟢      │    │     EXIT SHORT POSITION 🔴      │ │
│   ├─────────────────────────────────┤    ├─────────────────────────────────┤ │
│   │                                 │    │                                 │ │
│   │  Check if ANY turns bearish:   │    │  Check if ANY turns bullish:   │ │
│   │                                 │    │                                 │ │
│   │  • ST: 🟢→🔴 (Bearish)         │    │  • ST: 🔴→🟢 (Bullish)         │ │
│   │  • EMA_Low: 📈→📉 (Falling)    │    │  • EMA_High: 📉→📈 (Rising)    │ │
│   │  • EMA: 🟢→🔴 (Cross Down)     │    │  • EMA: 🔴→🟢 (Cross Up)       │ │
│   │                                 │    │                                 │ │
│   │  ANY TRUE? → EXIT LONG         │    │  ANY TRUE? → EXIT SHORT        │ │
│   │                                 │    │                                 │ │
│   └─────────────────────────────────┘    └─────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Example Scenarios

#### LONG Position Exit Scenarios
| Scenario | ST | EMA_Low | EMA | Action |
|----------|-----|---------|-----|--------|
| All Bullish | 🟢 | 📈 | 🟢 | **HOLD LONG** |
| ST Fails | 🔴 | 📈 | 🟢 | **EXIT LONG** |
| EMA_Low Fails | 🟢 | 📉 | 🟢 | **EXIT LONG** |
| EMA Fails | 🟢 | 📈 | 🔴 | **EXIT LONG** |

#### SHORT Position Exit Scenarios
| Scenario | ST | EMA_High | EMA | Action |
|----------|-----|----------|-----|--------|
| All Bearish | 🔴 | 📉 | 🔴 | **HOLD SHORT** |
| ST Fails | 🟢 | 📉 | 🔴 | **EXIT SHORT** |
| EMA_High Fails | 🔴 | 📈 | 🔴 | **EXIT SHORT** |
| EMA Fails | 🔴 | 📉 | 🟢 | **EXIT SHORT** |

---

## Risk Management

### Position Sizing
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Lot Size | 75 (NIFTY) | Standard NIFTY lot size |
| Max Position | 1 | Single position at a time |
| Stop Loss | **Indicator-Based** | Exit when 2-min conditions fail |
| Target | **Indicator-Based** | Ride trend until conditions fail |

### Risk Controls - Indicator-Based Exit
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                  INDICATOR-BASED RISK MANAGEMENT (BUY & SELL)                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   NO FIXED STOP LOSS OR TARGET                                               │
│   Exit is determined by 2-minute indicator conditions                        │
│                                                                               │
│   ┌─────────────────────────────────┐    ┌─────────────────────────────────┐ │
│   │      LONG POSITION 🟢           │    │      SHORT POSITION 🔴          │ │
│   ├─────────────────────────────────┤    ├─────────────────────────────────┤ │
│   │                                 │    │                                 │ │
│   │  HOLD while ALL BULLISH:       │    │  HOLD while ALL BEARISH:       │ │
│   │  • SuperTrend = 🟢 Bullish     │    │  • SuperTrend = 🔴 Bearish     │ │
│   │  • EMA Low = 📈 Rising         │    │  • EMA High = 📉 Falling       │ │
│   │  • EMA = 🟢 (8 > 9)            │    │  • EMA = 🔴 (8 < 9)            │ │
│   │                                 │    │                                 │ │
│   │  EXIT when ANY turns BEARISH:  │    │  EXIT when ANY turns BULLISH:  │ │
│   │  • SuperTrend → 🔴             │    │  • SuperTrend → 🟢             │ │
│   │  • EMA Low → 📉                │    │  • EMA High → 📈               │ │
│   │  • EMA → 🔴 (8 < 9)            │    │  • EMA → 🟢 (8 > 9)            │ │
│   │                                 │    │                                 │ │
│   └─────────────────────────────────┘    └─────────────────────────────────┘ │
│                                                                               │
│   Advantages:                                                                │
│   • Lets profits run in strong trends (both directions)                      │
│   • Quick exit on trend reversal                                             │
│   • No arbitrary price targets limiting gains                                │
│   • Dynamic stop based on market conditions                                  │
│   • Can profit in both bullish and bearish markets                          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture

### Component Diagram
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        NIFTY STRATEGY SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐ │
│  │   Kite Connect   │     │  NiftyBuyStrategy │     │    Indicators   │ │
│  │      API         │◀───▶│      Class        │◀───▶│    Functions    │ │
│  │                  │     │                   │     │                 │ │
│  │ • Authentication │     │ • Position Mgmt   │     │ • SuperTrend    │ │
│  │ • Historical Data│     │ • Signal Logic    │     │ • EMA           │ │
│  │ • Order Placement│     │ • Risk Management │     │ • RSI           │ │
│  │ • Quote Data     │     │ • State Tracking  │     │ • MACD          │ │
│  └──────────────────┘     └──────────────────┘     │ • StochRSI      │ │
│                                                     └─────────────────┘ │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                         DATA FLOW                                 │  │
│  │                                                                   │  │
│  │  Kite API ──▶ Historical Data ──▶ Indicators ──▶ Signal ──▶ Order│  │
│  │                                                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Class Structure
```
NiftyStrategy (BUY & SELL)
├── __init__(kite_client)
│   ├── Position tracking (position: LONG/SHORT/None, entry_price)
│   ├── Indicator parameters (supertrend, ema, rsi, macd)
│   └── Timing parameters (intervals, check frequencies)
│
├── get_nifty_instrument_token()
├── get_historical_data(interval, days)
│
├── # Entry Conditions
├── check_buy_conditions(df)      # All bullish 🟢 → Go LONG
├── check_sell_conditions(df)     # All bearish 🔴 → Go SHORT
│
├── # Exit Conditions (Indicator-Based)
├── check_exit_long(df)           # Any turns bearish 🔴 → Close LONG
├── check_exit_short(df)          # Any turns bullish 🟢 → Close SHORT
│
├── # Order Execution
├── place_buy_order(price)        # Enter LONG position
├── place_sell_order(price)       # Enter SHORT position
├── close_long_position(price)    # Exit LONG position
├── close_short_position(price)   # Exit SHORT position
│
├── print_status(df_5min, df_2min, signals)
└── run(simulation=True)
```

---

## Timing & Execution

### Polling Schedule
```
┌────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION TIMELINE                               │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Second:  0    5    10   15   20   25   30   35   40   45   50   55    │
│           │    │    │    │    │    │    │    │    │    │    │    │     │
│  5-min:   ✓         ✓         ✓         ✓         ✓         ✓         │
│  2-min:   ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    │
│                                                                         │
│  Legend:                                                                │
│  • 5-min check: Every 10 seconds (Primary signal)                      │
│  • 2-min check: Every 5 seconds (Confirmation + Exit monitoring)       │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Main Loop Logic
```python
while True:
    # Fetch data for both timeframes
    df_5min = get_historical_data("5minute")
    df_2min = get_historical_data("2minute")
    
    # Calculate indicators
    df_5min = calculate_all_indicators(df_5min)
    df_2min = calculate_all_indicators(df_2min)
    
    # Check PRIMARY every 10 seconds
    if time_elapsed >= 10:
        primary_buy_signal = check_buy_conditions(df_5min)    # All bullish 🟢
        primary_sell_signal = check_sell_conditions(df_5min)  # All bearish 🔴
    
    # Check CONFIRMATION every 5 seconds
    confirm_buy_signal = check_buy_conditions(df_2min)    # All bullish 🟢
    confirm_sell_signal = check_sell_conditions(df_2min)  # All bearish 🔴
    
    # Position management
    if position == 'LONG':
        if check_exit_long_conditions(df_2min):  # Any indicator turned bearish
            close_long_position()
    
    elif position == 'SHORT':
        if check_exit_short_conditions(df_2min):  # Any indicator turned bullish
            close_short_position()
    
    else:  # No position
        if primary_buy_signal AND confirm_buy_signal:
            place_buy_order()   # Go LONG 🟢
        
        elif primary_sell_signal AND confirm_sell_signal:
            place_sell_order()  # Go SHORT 🔴
    
    sleep(5)
```

---

## Consequences

### Positive
1. **Reduced False Signals** - Double confirmation filters out noise
2. **Trend Following** - Multiple indicators ensure trend alignment
3. **Quick Response** - 5-second checks for fast exit
4. **Risk Controlled** - Indicator-based exit limits downside dynamically
5. **Scalable** - Can be extended to other instruments

### Negative
1. **Missed Opportunities** - Strict conditions may miss some moves
2. **API Dependency** - Requires stable Kite Connect connection
3. **Latency** - 5-second minimum between checks
4. **Whipsaw Risk** - Rapid direction changes may cause frequent exits

### Risks
| Risk | Mitigation |
|------|------------|
| API Failure | Retry logic, error handling |
| Whipsaw Markets | Indicator-based exit, double confirmation |
| Slippage | Market orders, liquid instruments only |
| Gap Opens | Position sizing, overnight risk awareness |

---

## Configuration Parameters

```python
# Indicator Parameters
SUPERTREND_PERIOD = 7
SUPERTREND_MULTIPLIER = 3
EMA_LOW_PERIOD = 8
EMA_LOW_OFFSET = 9
EMA_FAST = 8
EMA_SLOW = 9
RSI_PERIOD = 14
MACD_FAST = 5
MACD_SLOW = 13
MACD_SIGNAL = 6

# Risk Parameters
# NO FIXED STOP LOSS OR TARGET - Exit based on indicator conditions
EXIT_ON_INDICATOR_FAIL = True   # Exit when any 2-min condition fails
LOT_SIZE = 75                   # NIFTY lot size

# Timing Parameters
PRIMARY_INTERVAL = "5minute"
CONFIRM_INTERVAL = "2minute"
PRIMARY_CHECK_SECONDS = 10
CONFIRM_CHECK_SECONDS = 5
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pandas | Latest | Data manipulation |
| numpy | Latest | Numerical calculations |
| kiteconnect | Latest | Zerodha API integration |
| python-dotenv | Latest | Environment variables |

---

## Testing Strategy

### Backtesting
- Use `backtest_double_confirm.py` for historical validation
- Test across different market conditions (trending, ranging)
- Validate indicator calculations against TradingView

### Paper Trading
- Run in `simulation=True` mode
- Monitor signal generation without real orders
- Validate entry/exit logic

### Live Trading
- Start with minimum lot size
- Monitor for first 10-20 trades
- Gradually increase position size

---

## Related Documents

- `nifty_strategy.py` - Main strategy implementation
- `backtest_double_confirm.py` - Backtesting framework
- `kite_client.py` - Kite API wrapper
- `config.py` - Configuration settings

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Team | Initial ADR - BUY strategy only |
| 2.0 | Jan 2026 | Team | Added SELL (SHORT) strategy with opposite conditions |
| 2.1 | Jan 2026 | Team | Updated to indicator-based exit (no fixed SL/Target) |
