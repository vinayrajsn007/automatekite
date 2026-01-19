# ADR-004: Integrated NIFTY CE Auto Trader

**Status:** Accepted  
**Date:** January 2026  
**Author:** Trading System Team  
**Deciders:** Strategy Development Team  
**Integrates:** ADR-001 (Double Confirmation), ADR-003 (Options Scanner)

---

## Context

We need an automated trading system that:
- Gets the current account balance to determine position sizing
- Takes NIFTY Options Expiry Date as user input
- Uses **ADR-003 Options Scanner** to select optimal CALL options (premium ₹80-₹120)
- Uses **ADR-001 Double Confirmation Strategy** to time entries and exits
- Automatically calculates quantity based on available balance (90% risk factor)
- Executes BUY when double confirmation triggers
- Executes SELL when exit conditions are met
- **Repeats the entire trading cycle after each exit until market closes**
- **Operates within market hours (9:15 AM - 3:30 PM IST)**
- **Tracks daily performance across multiple trades**

---

## Decision

We will implement an **Integrated NIFTY CE Auto Trader** that combines the Options Scanner for instrument selection with the Double Confirmation Strategy for trade timing. The system operates in a **continuous loop**, executing multiple trades throughout the trading day until market close.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     INTEGRATED NIFTY CE AUTO TRADER                               │
│                    (ADR-003 + ADR-001 Combined System)                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 1: INITIALIZATION                                                │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   1. Authenticate with Kite Connect                                     │   │
│   │   2. Get Current Account Balance                                        │   │
│   │   3. Accept Expiry Date Input from User                                 │   │
│   │   4. Display Available Balance & Trading Capacity                       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 2: OPTIONS SCANNER (ADR-003)                                     │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Filter NIFTY Options: Strike 25000-26000                           │   │
│   │   • Premium Range: ₹80-₹120                                             │   │
│   │   • Select Best CE Option (ATM or based on criteria)                   │   │
│   │   • Output: Selected CALL Option Instrument                             │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 3: QUANTITY CALCULATION                                          │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Available Margin = Balance × Risk Factor (default: 90%)            │   │
│   │   • Max Lots = Available Margin ÷ (Option Premium × Lot Size)          │   │
│   │   • Quantity = Max Lots × 75 (NIFTY Lot Size)                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 4: DOUBLE CONFIRMATION MONITORING (ADR-001)                      │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Monitor NIFTY Index with 5-min and 2-min timeframes                │   │
│   │   • Check: SuperTrend, EMA, RSI, MACD, StochRSI                        │   │
│   │   • Wait for BOTH timeframes to confirm BUY signal                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                     ┌──────────────┴──────────────┐                             │
│                     ▼                              ▼                             │
│   ┌─────────────────────────────┐  ┌─────────────────────────────┐             │
│   │  PHASE 5A: EXECUTE BUY      │  │  PHASE 5B: WAIT FOR SIGNAL  │             │
│   │  ────────────────────────   │  │  ────────────────────────── │             │
│   │  • CHECK BALANCE FIRST      │  │  • Continue Monitoring      │             │
│   │  • Recalculate Quantity     │  │  • Check Every 5 Seconds    │             │
│   │  • Verify Sufficient Funds  │  │  • Update Scanner Data      │             │
│   │  • Place BUY Order          │  │  • Re-evaluate Selection    │             │
│   │  • MARKET Order             │  │                             │             │
│   └─────────────────────────────┘  └─────────────────────────────┘             │
│                     │                                                            │
│                     ▼                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 6: EXIT MONITORING                                               │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Monitor 2-min timeframe for exit signals                           │   │
│   │   • Check: EMA Low Falling + Price Below EMA Low                       │   │
│   │   • Check: Strong Bearish Signal Override                              │   │
│   │   • Execute SELL when conditions met                                    │   │
│   │   • Force exit at market close (3:30 PM)                               │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 7: REPEAT CYCLE (CONTINUOUS TRADING)                            │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Record trade P&L to daily summary                                  │   │
│   │   • Check if market is still open (before 3:15 PM)                     │   │
│   │   • If YES: Go back to PHASE 1 (Refresh Balance, Re-scan Options)      │   │
│   │   • If NO: Stop trading, display daily summary                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW ARCHITECTURE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌───────────┐     ┌─────────────────────────────────────────────────────────┐  │
│  │   USER    │────▶│   INPUT: Expiry Date (e.g., "Jan 23" or "2026-01-23")   │  │
│  └───────────┘     └────────────────────────────┬────────────────────────────┘  │
│                                                  │                               │
│                                                  ▼                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         KITE CONNECT API                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │   │
│  │  │ kite.margins() │  │ instruments()  │  │ kite.historical_data()     │ │   │
│  │  │ Get Balance    │  │ Get Options    │  │ Get NIFTY OHLC Data        │ │   │
│  │  └───────┬────────┘  └───────┬────────┘  └─────────────┬──────────────┘ │   │
│  └──────────┼───────────────────┼─────────────────────────┼─────────────────┘   │
│             │                   │                         │                      │
│             ▼                   ▼                         ▼                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────────────┐   │
│  │ Account Balance │  │ Options Scanner │  │ Double Confirmation Strategy   │   │
│  │ ₹XX,XXX         │  │ (ADR-003)       │  │ (ADR-001)                      │   │
│  └────────┬────────┘  └────────┬────────┘  └───────────────┬────────────────┘   │
│           │                    │                           │                     │
│           │                    ▼                           │                     │
│           │         ┌───────────────────────┐             │                     │
│           │         │ Selected CE Option    │             │                     │
│           │         │ NIFTY26JAN25500CE     │             │                     │
│           │         │ Premium: ₹95          │             │                     │
│           │         └───────────┬───────────┘             │                     │
│           │                     │                          │                     │
│           └─────────────────────┼──────────────────────────┘                     │
│                                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      QUANTITY CALCULATOR                                  │   │
│  │                                                                           │   │
│  │  Available: ₹50,000  →  Premium: ₹95  →  Lot Size: 75                    │   │
│  │                                                                           │   │
│  │  Max Investment = ₹50,000 × 90% = ₹45,000                                │   │
│  │  Cost per Lot = ₹95 × 75 = ₹7,125                                        │   │
│  │  Max Lots = ₹45,000 ÷ ₹7,125 = 6 Lots                                    │   │
│  │  Quantity = 6 × 75 = 450                                                 │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                 │                                                │
│                                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     TRADING ENGINE                                        │   │
│  │                                                                           │   │
│  │  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐        │   │
│  │  │ WAIT STATE  │────────▶│ BUY ORDER   │────────▶│ POSITION    │        │   │
│  │  │ Monitoring  │  Signal │ Execute     │  Filled │ HOLDING     │        │   │
│  │  └─────────────┘         └─────────────┘         └──────┬──────┘        │   │
│  │                                                         │                │   │
│  │                                                   Exit  │                │   │
│  │                                                  Signal ▼                │   │
│  │                                                  ┌─────────────┐        │   │
│  │                                                  │ SELL ORDER  │        │   │
│  │                                                  │ Execute     │        │   │
│  │                                                  └─────────────┘        │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Expiry Date** | User Input | NIFTY Options expiry date |
| **Strike Min** | 25000 | Minimum strike price |
| **Strike Max** | 26000 | Maximum strike price |
| **Strike Multiple** | 100 | Only strikes in multiples of 100 |
| **Premium Min** | 80 | Minimum option premium |
| **Premium Max** | 120 | Maximum option premium |
| **Risk Factor** | 90% | Percentage of balance to use |
| **Lot Size** | 75 | NIFTY options lot size |
| **Scanner Refresh** | 5 seconds | Options scanner refresh rate |
| **Primary TF** | 5-minute | Double confirmation primary timeframe |
| **Confirm TF** | 2-minute | Double confirmation secondary timeframe |
| **Market Open** | 9:15 AM IST | Trading start time |
| **Market Close** | 3:30 PM IST | Trading end time |
| **Stop New Trades** | 15 minutes | Before market close |

---

## Balance & Quantity Calculation

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        BALANCE & QUANTITY CALCULATION                             │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   STEP 1: GET ACCOUNT BALANCE                                                    │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   margins = kite.margins(segment="equity")                                │ │
│   │   available_balance = margins['equity']['available']['live_balance']      │ │
│   │                                                                            │ │
│   │   Example Response:                                                        │ │
│   │   {                                                                        │ │
│   │     "equity": {                                                            │ │
│   │       "available": {                                                       │ │
│   │         "live_balance": 50000.00,                                         │ │
│   │         "adhoc_margin": 0,                                                │ │
│   │         "collateral": 0                                                   │ │
│   │       },                                                                   │ │
│   │       "utilised": { ... }                                                 │ │
│   │     }                                                                      │ │
│   │   }                                                                        │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 2: CALCULATE AVAILABLE MARGIN FOR TRADING                                │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   risk_factor = 0.90  # Use 90% of balance                                │ │
│   │   trading_capital = available_balance × risk_factor                       │ │
│   │                                                                            │ │
│   │   Example: ₹50,000 × 0.90 = ₹45,000 available for trading                 │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 3: GET SELECTED OPTION PREMIUM (FROM SCANNER)                            │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   selected_option = scanner.get_best_ce_option()                          │ │
│   │   option_premium = selected_option['ltp']  # e.g., ₹95                    │ │
│   │   lot_size = 75  # NIFTY lot size                                         │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 4: CALCULATE QUANTITY                                                     │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   cost_per_lot = option_premium × lot_size                                │ │
│   │   max_lots = floor(trading_capital ÷ cost_per_lot)                        │ │
│   │   quantity = max_lots × lot_size                                          │ │
│   │                                                                            │ │
│   │   Example:                                                                 │ │
│   │   ─────────                                                                │ │
│   │   cost_per_lot = ₹95 × 75 = ₹7,125                                        │ │
│   │   max_lots = floor(₹45,000 ÷ ₹7,125) = 6 lots                             │ │
│   │   quantity = 6 × 75 = 450 shares                                          │ │
│   │                                                                            │ │
│   │   Total Investment = 450 × ₹95 = ₹42,750                                  │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Option Selection Logic (From ADR-003)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        CE OPTION SELECTION CRITERIA                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   STEP 1: Get NIFTY Spot Price                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   nifty_ltp = kite.ltp("NSE:NIFTY 50")['NSE:NIFTY 50']['last_price']    │   │
│   │   Example: ₹25,480.50                                                    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 2: Calculate ATM Strike                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   atm_strike = round(nifty_ltp / 100) × 100                             │   │
│   │   Example: round(25480.50 / 100) × 100 = 25500                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 3: Filter Options (Premium ₹80-₹120)                                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   Available CE Options:                                                  │   │
│   │   ─────────────────────                                                  │   │
│   │   | Strike | Premium | Distance from ATM |                              │   │
│   │   |--------|---------|-------------------|                              │   │
│   │   | 25400  | ₹115.25 | -100 (ITM)        |                              │   │
│   │   | 25500  | ₹95.50  | 0 (ATM)           | ← SELECTED (Closest to ATM)  │   │
│   │   | 25600  | ₹82.75  | +100 (OTM)        |                              │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 4: Selection Priority                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Priority 1: ATM Strike CE (if premium in range)                       │   │
│   │   Priority 2: Nearest OTM CE (if ATM not in range)                      │   │
│   │   Priority 3: Nearest ITM CE (if no OTM in range)                       │   │
│   │                                                                          │   │
│   │   Selection = Option with premium closest to ₹100 (middle of range)     │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   OUTPUT: Selected Option                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   {                                                                      │   │
│   │     "tradingsymbol": "NIFTY26JAN25500CE",                               │   │
│   │     "instrument_token": 12345678,                                        │   │
│   │     "strike": 25500,                                                     │   │
│   │     "expiry": "2026-01-23",                                             │   │
│   │     "ltp": 95.50,                                                        │   │
│   │     "lot_size": 75                                                       │   │
│   │   }                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Double Confirmation Entry Logic (From ADR-001)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      DOUBLE CONFIRMATION BUY SIGNAL                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   5-MINUTE TIMEFRAME (Primary Signal)                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Check Every 10 Seconds:                                                │   │
│   │   ─────────────────────────                                              │   │
│   │   ✓ SuperTrend (7,3) Direction = 1 (Bullish)                            │   │
│   │   ✓ Close > SuperTrend Value                                            │   │
│   │   ✓ Close > EMA Low (8, offset 9)                                       │   │
│   │   ✓ EMA 8 > EMA 9 (Bullish Crossover)                                   │   │
│   │   ✓ StochRSI < 50 OR Rising                                             │   │
│   │   ✓ RSI < 65 AND Rising                                                 │   │
│   │   ✓ MACD Histogram > 0 OR Improving                                     │   │
│   │                                                                          │   │
│   │   PRIMARY_SIGNAL = All conditions TRUE                                   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   2-MINUTE TIMEFRAME (Confirmation Signal)                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Check Every 5 Seconds:                                                 │   │
│   │   ──────────────────────                                                 │   │
│   │   ✓ SuperTrend (7,3) Direction = 1 (Bullish)                            │   │
│   │   ✓ Close > SuperTrend Value                                            │   │
│   │   ✓ Close > EMA Low (8, offset 9)                                       │   │
│   │   ✓ EMA 8 > EMA 9 (Bullish Crossover)                                   │   │
│   │   ✓ StochRSI < 50 OR Rising                                             │   │
│   │   ✓ RSI < 65 AND Rising                                                 │   │
│   │   ✓ MACD Histogram > 0 OR Improving                                     │   │
│   │                                                                          │   │
│   │   CONFIRM_SIGNAL = All conditions TRUE                                   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   EXECUTE BUY (with Balance Check)                                              │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   if PRIMARY_SIGNAL AND CONFIRM_SIGNAL:                                 │   │
│   │       # STEP 1: Refresh balance before buying                           │   │
│   │       current_balance = kite.margins()['equity']['available']           │   │
│   │       trading_capital = current_balance × 0.90                          │   │
│   │                                                                          │   │
│   │       # STEP 2: Recalculate quantity with fresh balance                 │   │
│   │       quantity = recalculate_quantity(trading_capital, option_premium)  │   │
│   │                                                                          │   │
│   │       # STEP 3: Verify sufficient balance                               │   │
│   │       if quantity > 0:                                                  │   │
│   │           buy_option(                                                    │   │
│   │               tradingsymbol = selected_ce_option['tradingsymbol'],      │   │
│   │               quantity = quantity,                                       │   │
│   │               order_type = "MARKET"                                     │   │
│   │           )                                                              │   │
│   │       else:                                                              │   │
│   │           log("Insufficient balance - waiting 1 minute")                │   │
│   │           sleep(60)  # Wait 1 minute                                    │   │
│   │           GOTO STEP 1  # Re-scan options, wait for new signal           │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Exit Conditions (From ADR-001)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          EXIT (SELL) CONDITIONS                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   MONITORED ON 2-MINUTE TIMEFRAME (Every 5 Seconds)                              │
│                                                                                   │
│   EXIT TRIGGER 1: EMA LOW FALLING                                                │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   ema_low_falling = (                                                    │   │
│   │       current['ema_low_8'] < previous['ema_low_8'] AND                  │   │
│   │       previous['ema_low_8'] < prev2['ema_low_8']                        │   │
│   │   )                                                                      │   │
│   │                                                                          │   │
│   │   price_below_ema = close < ema_low_8                                   │   │
│   │                                                                          │   │
│   │   SELL if: ema_low_falling AND price_below_ema                          │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   EXIT TRIGGER 2: STRONG BEARISH SIGNAL                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   strong_bearish = (                                                     │   │
│   │       supertrend_direction == -1 AND    # Bearish SuperTrend            │   │
│   │       ema_8 < ema_9 AND                 # EMA Crossed Down              │   │
│   │       close < ema_low_8                 # Price Below EMA Low           │   │
│   │   )                                                                      │   │
│   │                                                                          │   │
│   │   SELL if: strong_bearish                                               │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   SELL ORDER EXECUTION                                                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   if exit_trigger_1 OR exit_trigger_2:                                  │   │
│   │       sell_option(                                                       │   │
│   │           tradingsymbol = held_option['tradingsymbol'],                 │   │
│   │           quantity = position_quantity,                                  │   │
│   │           order_type = "MARKET"                                         │   │
│   │       )                                                                  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Continuous Trading Mode

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         CONTINUOUS TRADING MODE                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   MARKET HOURS: 9:15 AM - 3:30 PM IST                                            │
│   ═══════════════════════════════════════════════════════════════════════════    │
│                                                                                   │
│   9:15 AM                                                           3:30 PM      │
│      │                                                                  │        │
│      │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │        │
│      │  │Trade │ │Trade │ │Trade │ │Trade │ │Trade │    ...      │        │
│      │  │  #1  │ │  #2  │ │  #3  │ │  #4  │ │  #5  │             │        │
│      │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘             │        │
│      │                                                                  │        │
│      ├──────────────────────────────────────────────────────────┬───────┤        │
│      │              ACTIVE TRADING ZONE                          │ STOP  │        │
│      │         (New trades allowed)                              │ ZONE  │        │
│      │                                                           │15 min │        │
│      └──────────────────────────────────────────────────────────┴───────┘        │
│                                                                                   │
│   TRADE CYCLE FLOW:                                                              │
│   ─────────────────                                                              │
│                                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │  START → [Scan Options] → [Wait for Double Confirmation]                │   │
│   │    ▲                                 │                                   │   │
│   │    │                                 ▼                                   │   │
│   │    │                     [CHECK BALANCE] → [Recalc Qty]                  │   │
│   │    │                           │                │                        │   │
│   │    │              Insufficient │                │ OK                     │   │
│   │    │                           ▼                ▼                        │   │
│   │    │                    [WAIT 1 MIN]      [BUY] ──▶ [Hold Position]     │   │
│   │    │                           │                                         │   │
│   │    └───────────────────────────┘                                         │   │
│   │            ▲                                      │                      │   │
│   │            │                                 EXIT │                      │   │
│   │            │                                      ▼                      │   │
│   │            │◄────── [Record P&L] ◄────── [Execute SELL]                 │   │
│   │            │                                                             │   │
│   │         REPEAT (if market still open)                                   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   SAFETY FEATURES:                                                               │
│   ────────────────                                                               │
│   • No new trades initiated within 15 minutes of market close                   │
│   • Any open position is force-exited at market close (3:30 PM)                 │
│   • **Balance is checked immediately BEFORE each BUY order**                    │
│   • Quantity is recalculated with fresh balance before buying                   │
│   • **If insufficient balance → Wait 1 minute → Restart from Step 1**          │
│   • Options are re-scanned for each new trade (may select different strike)     │
│                                                                                   │
│   DAILY TRACKING:                                                                │
│   ───────────────                                                                │
│   • Each trade recorded with entry/exit prices, P&L, exit reason                │
│   • Running total P&L displayed throughout the day                              │
│   • Full daily summary displayed at end of trading session                      │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Execution Timeline

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE EXECUTION TIMELINE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  STARTUP PHASE                                                                   │
│  ─────────────                                                                   │
│  T+0s:   Authenticate with Kite Connect                                          │
│  T+1s:   Get Account Balance                                                     │
│  T+2s:   User Inputs Expiry Date                                                 │
│  T+3s:   Load NIFTY Options (NFO instruments)                                    │
│  T+4s:   Initial Scanner Run - Select CE Option                                  │
│  T+5s:   Calculate Quantity Based on Balance                                     │
│  T+6s:   Display Ready Status                                                    │
│                                                                                   │
│  MONITORING PHASE (No Position)                                                  │
│  ─────────────────────────────                                                   │
│  │                                                                               │
│  │  Second:  0    5    10   15   20   25   30   35   40   45   50   55         │
│  │           │    │    │    │    │    │    │    │    │    │    │    │          │
│  │  5-min:   ✓         ✓         ✓         ✓         ✓         ✓              │
│  │  2-min:   ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │  Scanner: ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │                                                                               │
│  │  Actions per 5-second cycle:                                                 │
│  │  • Refresh option premium via scanner                                        │
│  │  • Check 2-min confirmation signal                                           │
│  │  • If 10s elapsed: Check 5-min primary signal                                │
│  │  • If BOTH signals TRUE:                                                     │
│  │      → CHECK BALANCE (fresh)                                                 │
│  │      → Recalculate quantity                                                  │
│  │      → If sufficient funds: Execute BUY                                      │
│  │      → If insufficient: WAIT 1 MINUTE → RESTART FROM STEP 1                 │
│  │                                                                               │
│  HOLDING PHASE (Position Active)                                                 │
│  ───────────────────────────────                                                 │
│  │                                                                               │
│  │  Second:  0    5    10   15   20   25   30   35   40   45   50   55         │
│  │           │    │    │    │    │    │    │    │    │    │    │    │          │
│  │  2-min:   ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │  Exit:    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │                                                                               │
│  │  Actions per 5-second cycle:                                                 │
│  │  • Check EMA Low Falling condition                                           │
│  │  • Check Strong Bearish signal                                               │
│  │  • If EXIT condition TRUE: Execute SELL                                      │
│  │                                                                               │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## State Machine (Continuous Trading)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    STATE MACHINE - CONTINUOUS TRADING MODE                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│                         ┌─────────────────────┐                                  │
│                         │    INITIALIZING     │                                  │
│                         │  • Accept Expiry    │                                  │
│                         │  • Load Options     │                                  │
│                         └──────────┬──────────┘                                  │
│                                    │                                             │
│  ┌─────────────────────────────────┼─────────────────────────────────────────┐  │
│  │                                 ▼                                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    TRADE CYCLE START                                 │  │  │
│  │  │  ─────────────────────────────────────────────────────────────────  │  │  │
│  │  │   1. Check Market Hours (9:15 AM - 3:30 PM IST)                     │  │  │
│  │  │   2. Refresh Account Balance                                         │  │  │
│  │  │   3. Scan & Select New CE Option                                    │  │  │
│  │  │   4. Calculate Quantity (90% of balance)                            │  │  │
│  │  └──────────────────────────────┬──────────────────────────────────────┘  │  │
│  │                                 │                                          │  │
│  │                                 ▼                                          │  │
│  │  ┌─────────────────────┐          ┌─────────────────────┐                 │  │
│  │  │    WAITING_BUY      │          │   POSITION_OPEN     │                 │  │
│  │  │  • Monitor 5-min    │  BUY     │  • Monitor 2-min    │                 │  │
│  │  │  • Monitor 2-min    │─────────▶│  • Check Exit       │                 │  │
│  │  │  • Update Scanner   │  Signal  │  • Track P&L        │                 │  │
│  │  └─────────────────────┘          └──────────┬──────────┘                 │  │
│  │                                              │                             │  │
│  │                                        EXIT  │                             │  │
│  │                                       Signal │                             │  │
│  │                                              ▼                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    TRADE COMPLETED                                   │  │  │
│  │  │  ─────────────────────────────────────────────────────────────────  │  │  │
│  │  │   • Record Trade P&L                                                │  │  │
│  │  │   • Update Daily Summary                                            │  │  │
│  │  │   • Check: Market still open? (before 3:15 PM)                      │  │  │
│  │  │   • If YES → REPEAT (Go to TRADE CYCLE START)                       │  │  │
│  │  │   • If NO  → Exit to DAILY SUMMARY                                  │  │  │
│  │  └──────────────────────────────┬──────────────────────────────────────┘  │  │
│  │                                 │                                          │  │
│  │                    CONTINUOUS TRADING LOOP                                 │  │
│  │                 (Repeats until market closes)                              │  │
│  └─────────────────────────────────┼─────────────────────────────────────────┘  │
│                                    │                                             │
│                                    │ Market Close (3:30 PM) / Manual Stop        │
│                                    ▼                                             │
│                         ┌─────────────────────┐                                  │
│                         │   DAILY SUMMARY     │                                  │
│                         │  • Total Trades     │                                  │
│                         │  • Total P&L        │                                  │
│                         │  • Trade Details    │                                  │
│                         └─────────────────────┘                                  │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Display Output Format

```
════════════════════════════════════════════════════════════════════════════════════
  NIFTY CE AUTO TRADER - 2026-01-23 10:35:15
  MODE: CONTINUOUS TRADING | TRADE CYCLE #2
════════════════════════════════════════════════════════════════════════════════════

  MARKET STATUS
  ────────────────────────────────────────────────────────────────────────────────
  Market: OPEN | Time to Close: 295 minutes
  
  ACCOUNT STATUS
  ────────────────────────────────────────────────────────────────────────────────
  Available Balance: ₹50,000.00
  Trading Capital (90%): ₹45,000.00
  
  SELECTED OPTION (via ADR-003 Scanner)
  ────────────────────────────────────────────────────────────────────────────────
  Symbol: NIFTY26JAN25500CE
  Strike: 25500 (ATM)
  Expiry: 23-Jan-2026
  Current Premium: ₹95.50
  Lot Size: 75
  
  QUANTITY CALCULATION
  ────────────────────────────────────────────────────────────────────────────────
  Cost per Lot: ₹95.50 × 75 = ₹7,162.50
  Max Lots: floor(₹45,000 / ₹7,162.50) = 6 Lots
  Trading Quantity: 6 × 75 = 450
  Total Investment: ₹42,975.00

  DOUBLE CONFIRMATION STATUS (ADR-001)
  ────────────────────────────────────────────────────────────────────────────────
  NIFTY Spot: ₹25,480.50
  
  | Indicator      | 5-MIN   | 2-MIN   | Status  |
  |----------------|---------|---------|---------|
  | SuperTrend     | BULLISH | BULLISH | ✓       |
  | Price > ST     | YES     | YES     | ✓       |
  | EMA Cross      | 8 > 9   | 8 > 9   | ✓       |
  | Price > EMA Lo | YES     | YES     | ✓       |
  | StochRSI       | 35.2    | 42.1    | ✓       |
  | RSI            | 58.5    | 55.2    | ✓       |
  | MACD Hist      | +2.15   | +1.85   | ✓       |
  
  PRIMARY SIGNAL (5-min): ✓ BUY
  CONFIRM SIGNAL (2-min): ✓ BUY
  
  ═══════════════════════════════════════════════════════════════════════════════
  >>> DOUBLE CONFIRMATION ACHIEVED - EXECUTING BUY ORDER <<<
  ═══════════════════════════════════════════════════════════════════════════════
  
  ORDER DETAILS
  ────────────────────────────────────────────────────────────────────────────────
  Order Type: MARKET BUY
  Symbol: NIFTY26JAN25500CE
  Quantity: 450
  Expected Cost: ₹42,975.00
  Order ID: 230123000012345

════════════════════════════════════════════════════════════════════════════════════
  Status: POSITION OPEN | Entry: ₹95.50 | Current: ₹97.25 | P&L: +₹787.50 (+1.83%)
════════════════════════════════════════════════════════════════════════════════════
```

### Daily Summary Output (End of Day)

```
════════════════════════════════════════════════════════════════════════════════════
  DAILY TRADING SUMMARY - 2026-01-23
════════════════════════════════════════════════════════════════════════════════════
  Total Trades: 4
  Total P&L: ₹3,250.00

  TRADE DETAILS:
  ──────────────────────────────────────────────────────────────────────────────────
  #1: NIFTY26JAN25500CE | Entry ₹95.50 → Exit ₹98.25 | P&L: +₹1,237.50 | ema_low_falling
  #2: NIFTY26JAN25400CE | Entry ₹112.00 → Exit ₹108.50 | P&L: -₹1,575.00 | strong_bearish
  #3: NIFTY26JAN25500CE | Entry ₹94.00 → Exit ₹99.00 | P&L: +₹2,250.00 | ema_low_falling
  #4: NIFTY26JAN25600CE | Entry ₹82.00 → Exit ₹85.00 | P&L: +₹1,337.50 | market_close
════════════════════════════════════════════════════════════════════════════════════
  Goodbye!
```

---

## Class Structure

```
IntegratedNiftyCETrader
├── __init__(kite_client, config)
│   ├── KiteClient for API access
│   ├── Account balance tracking
│   ├── Scanner configuration (from ADR-003)
│   ├── Strategy configuration (from ADR-001)
│   ├── Position state management
│   ├── Order tracking
│   └── Daily trade history tracking
│
├── INITIALIZATION METHODS
│   ├── get_account_balance()
│   │   └── Fetch available balance from kite.margins()
│   │
│   ├── get_expiry_date_input()
│   │   └── Accept and parse user expiry date input
│   │
│   └── display_trading_capacity()
│       └── Show balance and max lots available
│
├── MARKET HOURS METHODS (NEW)
│   ├── is_market_open()
│   │   └── Check if current time is within 9:15 AM - 3:30 PM IST
│   │
│   ├── get_time_to_market_close()
│   │   └── Return minutes remaining until market closes
│   │
│   └── should_stop_new_trades()
│       └── Check if < 15 minutes to market close
│
├── OPTIONS SCANNER METHODS (ADR-003)
│   ├── load_nifty_options(expiry_date)
│   │   └── Load all NIFTY options for given expiry
│   │
│   ├── filter_by_premium_range(options)
│   │   └── Filter options with premium ₹80-₹120
│   │
│   ├── get_nifty_spot_price()
│   │   └── Get current NIFTY index price
│   │
│   └── select_best_ce_option()
│       └── Select ATM or nearest suitable CE option
│
├── QUANTITY CALCULATOR
│   └── calculate_quantity(option_premium)
│       ├── Apply 90% risk factor to balance
│       ├── Calculate max lots affordable
│       └── Return quantity (lots × lot_size)
│
├── DOUBLE CONFIRMATION METHODS (ADR-001)
│   ├── get_historical_data(interval)
│   │   └── Fetch NIFTY OHLC data
│   │
│   ├── calculate_indicators(df)
│   │   └── Calculate SuperTrend, EMA, RSI, MACD, StochRSI
│   │
│   ├── check_buy_conditions(df, timeframe)
│   │   └── Check all indicator conditions for buy
│   │
│   └── check_exit_conditions(df_2min)
│       └── Check EMA falling and bearish signals
│
├── ORDER EXECUTION
│   ├── place_buy_order(symbol, quantity)
│   │   └── Execute market buy order
│   │
│   ├── place_sell_order(symbol, quantity, reason)
│   │   └── Execute market sell order
│   │
│   └── get_order_status(order_id)
│       └── Check order fill status
│
├── DISPLAY & LOGGING
│   ├── display_status()
│   │   └── Show current state, signals, position, trade cycle #
│   │
│   └── log_trade(trade_type, details)
│       └── Log trade to daily_trades list
│
└── MAIN EXECUTION (CONTINUOUS LOOP)
    └── run()
        ├── Initialize and get expiry date (once)
        │
        └── WHILE market is open:
            ├── Check market hours
            ├── Refresh account balance
            ├── Scan and select new CE option
            ├── Calculate quantity
            ├── Wait for double confirmation BUY signal
            ├── Execute BUY
            ├── Monitor for EXIT conditions
            ├── Execute SELL
            ├── Record trade P&L to daily summary
            └── REPEAT (loop back to start)
            
        └── ON market close or manual stop:
            ├── Force exit any open position
            └── Display daily trading summary
```

---

## API Endpoints Used

| API Method | Purpose | Frequency |
|------------|---------|-----------|
| `kite.margins("equity")` | Get account balance | **Before each BUY order** |
| `kite.instruments("NFO")` | Load options chain | On startup |
| `kite.ltp(symbols)` | Get option premiums | Every 5 seconds |
| `kite.historical_data()` | Get NIFTY OHLC | Every 5 seconds |
| `kite.place_order()` | Execute trades | On signal |
| `kite.order_history()` | Check order status | After order |
| `kite.positions()` | Verify positions | After order |

---

## Error Handling

| Error | Handling | Recovery |
|-------|----------|----------|
| Insufficient Balance | Alert user, reduce quantity | Wait for deposit |
| No Options in Range | Expand premium range | Use nearest option |
| API Rate Limit | Exponential backoff | Retry with delay |
| Order Rejected | Log reason, alert | Manual intervention |
| Network Timeout | Retry 3 times | Continue monitoring |
| Position Mismatch | Reconcile with API | Verify positions |

---

## Configuration File

```python
# config.py - Integrated Trader Configuration

TRADER_CONFIG = {
    # User Input
    "expiry_date": None,  # Set via user input
    
    # Options Scanner (ADR-003)
    "strike_min": 25000,
    "strike_max": 26000,
    "strike_multiple": 100,
    "premium_min": 80,
    "premium_max": 120,
    "scanner_refresh_seconds": 5,
    
    # Quantity Calculation
    "risk_factor": 0.90,  # Use 90% of balance
    "lot_size": 75,       # NIFTY lot size
    
    # Market Hours (IST)
    "market_open_hour": 9,
    "market_open_minute": 15,
    "market_close_hour": 15,
    "market_close_minute": 30,
    "stop_new_trades_minutes": 15,  # Stop new trades 15 min before close
    
    # Double Confirmation (ADR-001)
    "primary_timeframe": "5minute",
    "confirm_timeframe": "2minute",
    "primary_check_seconds": 10,
    "confirm_check_seconds": 5,
    
    # Indicator Parameters
    "supertrend_period": 7,
    "supertrend_multiplier": 3,
    "ema_low_period": 8,
    "ema_low_offset": 9,
    "ema_fast": 8,
    "ema_slow": 9,
    "rsi_period": 14,
    "macd_fast": 5,
    "macd_slow": 13,
    "macd_signal": 6,
    
    # Trading
    "exchange": "NFO",
    "product_type": "MIS",  # Intraday
    "order_type": "MARKET",
    
    # Continuous Trading
    "continuous_mode": True,  # Repeat trades until market close
}
```

---

## Usage

### Interactive Mode
```bash
python integrated_nifty_ce_trader.py
```

### Programmatic Mode
```python
from integrated_nifty_ce_trader import IntegratedNiftyCETrader

# Initialize trader
trader = IntegratedNiftyCETrader()

# Run with expiry date
trader.run(expiry_date="Jan 23")

# Or with explicit configuration
config = {
    "expiry_date": "Jan 23",
    "risk_factor": 0.50,  # Use 50% of balance
    "premium_min": 70,
    "premium_max": 130
}
trader.run_with_config(config)
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pandas | Latest | Data manipulation |
| numpy | Latest | Numerical calculations |
| kiteconnect | Latest | Zerodha API integration |
| python-dotenv | Latest | Environment variables |
| tabulate | Latest | Pretty table output |

---

## Related Documents

- `ADR-001-NIFTY-DOUBLE-CONFIRMATION-OPTION-CE-BUY-STRATEGY BUY.md` - Double confirmation strategy
- `ADR-003-NIFTY-OPTIONS-SCANNER.md` - Options scanner strategy
- `integrated_nifty_ce_trader.py` - Main implementation
- `kite_client.py` - Kite API wrapper

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Team | Initial Integrated ADR combining ADR-001 and ADR-003 |
| 1.1 | Jan 2026 | Team | Updated risk factor 80% → 90%, Added continuous trading loop until market close, Added market hours checking (9:15 AM - 3:30 PM IST), Added daily P&L tracking across multiple trades, Added safety features (stop new trades 15 min before close, force exit at close) |
| 1.2 | Jan 2026 | Team | Balance check moved to immediately BEFORE each BUY order, Quantity recalculated with fresh balance before buying, If insufficient balance → wait 1 minute → restart from Step 1 (re-scan options, wait for new signal) |
