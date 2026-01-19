# ADR-001: NIFTY 50 Double Confirmation Buy Strategy

**Status:** Accepted  
**Date:** January 2026  
**Author:** Trading System Team  
**Deciders:** Strategy Development Team

---

## Context

We need an automated trading strategy for NIFTY 50 index that:
- Minimizes false signals through multi-timeframe confirmation
- Uses proven technical indicators for trend identification
- Implements proper risk management with technical exit signals
- Can operate in both simulation and live trading modes
- Integrates with Zerodha Kite Connect API

---

## Decision

We will implement a **Double Confirmation Buy Strategy** that requires alignment of technical indicators on **two separate timeframes** (5-minute and 2-minute) before executing trades.

---

## Strategy Architecture

### 1. Multi-Timeframe Approach

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOUBLE CONFIRMATION SYSTEM                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   PRIMARY TIMEFRAME (5-minute)     CONFIRMATION TIMEFRAME (2-min)│
│   ┌─────────────────────────┐      ┌─────────────────────────┐  │
│   │  Check every 10 seconds │      │  Check every 5 seconds  │  │
│   │                         │      │                         │  │
│   │  • SuperTrend (7,3)     │      │  • SuperTrend (7,3)     │  │
│   │  • EMA Low (8, offset 9)│      │  • EMA Low (8, offset 9)│  │
│   │  • EMA Crossover (8,9)  │      │  • EMA Crossover (8,9)  │  │
│   │  • StochasticRSI        │      │  • StochasticRSI        │  │
│   │  • RSI (14)             │      │  • RSI (14)             │  │
│   │  • MACD (5,13,6)        │      │  • MACD (5,13,6)        │  │
│   └───────────┬─────────────┘      └───────────┬─────────────┘  │
│               │                                 │                │
│               └──────────┬──────────────────────┘                │
│                          │                                       │
│                          ▼                                       │
│               ┌─────────────────────┐                           │
│               │  BOTH MUST BE TRUE  │                           │
│               │    TO EXECUTE BUY   │                           │
│               └──────────┬──────────┘                           │
│                          │                                       │
│                          ▼                                       │
│               ┌─────────────────────┐                           │
│               │   PLACE BUY ORDER   │                           │
│               └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Technical Indicators

| Indicator | Parameters | Purpose | Buy Condition |
|-----------|------------|---------|---------------|
| **SuperTrend** | Period: 7, Multiplier: 3 | Primary trend identification | Direction = 1 (Bullish), Price > SuperTrend |
| **EMA on Low** | Period: 8, Offset: 9 | Support level tracking | Price > EMA Low, EMA Rising |
| **EMA Crossover** | Fast: 8, Slow: 9 | Momentum confirmation | EMA 8 > EMA 9 |
| **Stochastic RSI** | RSI: 14, Stoch: 14, K: 3, D: 3 | Oversold/momentum | < 50 or Rising |
| **RSI** | Period: 14 | Overbought/oversold filter | < 65 and Rising |
| **MACD** | Fast: 5, Slow: 13, Signal: 6 | Momentum confirmation | Histogram > 0 or Improving |

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

## Buy Conditions (All Must Be True)

### Primary Conditions (5-minute)
```python
all_conditions_met = (
    supertrend_direction == 1           # SuperTrend Bullish
    AND close > supertrend_value        # Price above SuperTrend
    AND close > ema_low_8               # Price above EMA Low
    AND ema_8 > ema_9                   # EMA Bullish crossover
    AND (stoch_rsi_k < 50 OR rising)    # StochRSI good
    AND (rsi_14 < 65 AND rising)        # RSI not overbought
    AND (macd_hist > 0 OR improving)    # MACD positive momentum
)
```

### Confirmation Conditions (2-minute)
Same indicators must confirm on the shorter timeframe.

### Strong Signal Override
```python
crossover_signal = supertrend_crossover OR ema_crossover
is_buy = all_conditions_met OR (crossover_signal AND supertrend_bullish AND ema_bullish)
```

---

## Sell Conditions

### Exit Triggers (Priority Order)

| Priority | Condition | Check Frequency | Action |
|----------|-----------|-----------------|--------|
| 1 | EMA Low (8) Falling | Every 5 seconds | SELL |
| 2 | Strong Bearish Signal | Every 5 seconds | SELL |

### Sell Logic (2-minute timeframe)
```python
# Primary sell condition
ema_low_falling = (
    curr['ema_low_8'] < prev['ema_low_8'] AND
    prev['ema_low_8'] < prev2['ema_low_8']
)
price_below_ema_low = close < ema_low_8

is_sell = ema_low_falling AND price_below_ema_low

# Strong bearish override
strong_sell = (
    supertrend_direction == -1 AND  # Bearish
    ema_8 < ema_9 AND               # EMA crossed down
    price_below_ema_low
)
```

---

## Risk Management

### Position Sizing
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Lot Size | 75 (NIFTY) | Standard NIFTY lot size |
| Max Position | 1 | Single position at a time |


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
NiftyBuyStrategy
├── __init__(kite_client)
│   ├── Position tracking (position, entry_price)
│   ├── Indicator parameters (supertrend, ema, rsi, macd)
│   └── Timing parameters (intervals, check frequencies)
│
├── get_nifty_instrument_token()
├── get_historical_data(interval, days)
├── check_buy_conditions(df, timeframe_name)
├── check_sell_condition_2min(df)
├── print_status(df_5min, df_2min, primary_signal, confirm_signal)
├── place_buy_order(price)
├── place_sell_order(price, reason)
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
        primary_signal = check_buy_conditions(df_5min)
    
    # Check CONFIRMATION every 5 seconds
    confirm_signal = check_buy_conditions(df_2min)
    
    # Position management
    if position == 'LONG':
        check_exit_conditions()  # EMA falling, bearish signals
    else:
        if primary_signal AND confirm_signal:
            place_buy_order()
    
    sleep(5)
```

---

## Consequences

### Positive
1. **Reduced False Signals** - Double confirmation filters out noise
2. **Trend Following** - Multiple indicators ensure trend alignment
3. **Quick Response** - 5-second checks for fast exit
4. **Scalable** - Can be extended to other instruments

### Negative
1. **Missed Opportunities** - Strict conditions may miss some moves
2. **API Dependency** - Requires stable Kite Connect connection
3. **Latency** - 5-second minimum between checks
4. **Single Direction** - Only BUY strategy, misses short opportunities

### Risks
| Risk | Mitigation |
|------|------------|
| API Failure | Retry logic, error handling |
| Whipsaw Markets | Double confirmation, technical exit signals |
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
LOT_SIZE = 75            # NIFTY lot size

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
| 1.0 | Jan 2026 | Team | Initial ADR |
