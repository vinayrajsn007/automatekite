# ADR-003: NIFTY Options Scanner - Premium Range Filter

**Status:** Accepted  
**Date:** January 2026  
**Author:** Trading System Team  
**Deciders:** Strategy Development Team

---

## Context

We need an automated options scanner for NIFTY that:
- Fetches all NIFTY options within a specific strike price range (25000-26000)
- Gets live market data (LTP) for both Call (CE) and Put (PE) options
- Filters options based on premium range (80-120 INR)
- Runs continuously every 5 seconds for real-time monitoring
- Integrates with Zerodha Kite Connect API for live market data

---

## Decision

We will implement a **NIFTY Options Scanner** that continuously monitors NIFTY options in the 25000-26000 strike range and filters those with premiums between ₹80 and ₹120.

---

## Strategy Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    NIFTY OPTIONS PREMIUM SCANNER                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   STEP 1: Get All NIFTY Options (NFO Exchange)                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   • Filter: Strike Price >= 25000 AND Strike Price <= 26000         │   │
│   │   • Include: Both CE (Call) and PE (Put) options                    │   │
│   │   • Expiry: Weekly/Monthly (configurable)                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│   STEP 2: Fetch Live Quotes (LTP) from Kite                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   • Get LTP for all filtered options                                │   │
│   │   • Uses kite.ltp() or kite.quote() API                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│   STEP 3: Filter by Premium Range                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   • Keep options where: LTP > 80 AND LTP < 120                     │   │
│   │   • Display CE and PE separately                                    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│   STEP 4: Refresh Every 5 Seconds                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   • Continuous loop with 5-second interval                          │   │
│   │   • Real-time updates during market hours                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW DIAGRAM                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────┐                                                         │
│  │  Kite Connect   │                                                         │
│  │      API        │                                                         │
│  └────────┬────────┘                                                         │
│           │                                                                   │
│           ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              kite.instruments("NFO")                                │    │
│  │              Returns: All NFO instruments                           │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │   FILTER STEP 1: NIFTY Options Only                                 │    │
│  │   • name == "NIFTY"                                                 │    │
│  │   • instrument_type in ["CE", "PE"]                                 │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │   FILTER STEP 2: Strike Range                                       │    │
│  │   • strike >= 25000                                                 │    │
│  │   • strike <= 26000                                                 │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              kite.ltp(instruments_list)                             │    │
│  │              Returns: Live LTP for each option                      │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │   FILTER STEP 3: Premium Range                                      │    │
│  │   • LTP > 80                                                        │    │
│  │   • LTP < 120                                                       │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │   OUTPUT: Filtered CE and PE Options                                │    │
│  │   Display: Symbol, Strike, LTP, Change%, Expiry                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Expiry Date** | User Input | Specific expiry date (e.g., "Jan 20", "20 Jan 2026") |
| **Strike Min** | 25000 | Minimum strike price |
| **Strike Max** | 26000 | Maximum strike price |
| **Strike Multiple** | 100 | Only strikes in multiples of 100 (25000, 25100, 25200...) |
| **Premium Min** | 80 | Minimum LTP filter |
| **Premium Max** | 120 | Maximum LTP filter |
| **Refresh Interval** | 5 seconds | How often to fetch live data |
| **Exchange** | NFO | National Stock Exchange F&O segment |
| **Underlying** | NIFTY | NIFTY 50 Index |

### Strike Multiple Filter

NIFTY options have strikes in multiples of 50 (e.g., 25000, 25050, 25100, 25150...). 
Setting `strike_multiple=100` filters to only show strikes in multiples of 100:

```
With strike_multiple=100:
  ✓ 25000, 25100, 25200, 25300, 25400, 25500, 25600, 25700, 25800, 25900, 26000
  
Excluded (multiples of 50 but not 100):
  ✗ 25050, 25150, 25250, 25350, 25450, 25550, 25650, 25750, 25850, 25950
```

---

## Expiry Date Input

### Supported Formats

The scanner accepts expiry date in multiple formats:

| Format | Example | Notes |
|--------|---------|-------|
| Month Day | `Jan 20` or `January 20` | Uses current year |
| Day Month | `20 Jan` or `20 January` | Uses current year |
| Month Day Year | `Jan 20 2026` | Full date |
| Day Month Year | `20 Jan 2026` | Full date |
| ISO Format | `2026-01-20` | Standard format |
| Slash Format | `20/01/2026` | DD/MM/YYYY |

### User Input Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          EXPIRY DATE INPUT                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   Available NIFTY Expiry Dates:                                              │
│   ----------------------------------------                                    │
│     1. 20-Jan-2026 (Monday)                                                  │
│     2. 23-Jan-2026 (Thursday)                                                │
│     3. 30-Jan-2026 (Thursday)                                                │
│     4. 06-Feb-2026 (Thursday)                                                │
│     ... and more                                                              │
│                                                                               │
│   Enter expiry date in any of these formats:                                 │
│     - 'Jan 20' or '20 Jan'                                                   │
│     - 'Jan 20 2026' or '20 Jan 2026'                                        │
│     - '2026-01-20' (ISO format)                                              │
│     - Press Enter for nearest weekly expiry                                  │
│   ────────────────────────────────────────────────────────────────────       │
│                                                                               │
│   Enter Expiry Date (e.g., Jan 20): █                                        │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Execution Timeline

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION TIMELINE                                   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Second:  0    5    10   15   20   25   30   35   40   45   50   55       │
│           │    │    │    │    │    │    │    │    │    │    │    │        │
│  Fetch:   ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓       │
│                                                                             │
│  Actions per cycle:                                                         │
│  • Fetch LTP for all options in range                                      │
│  • Filter by premium (80-120)                                              │
│  • Display filtered CE and PE options                                      │
│  • Sleep 5 seconds                                                          │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Output Display Format

```
════════════════════════════════════════════════════════════════════════════════
  NIFTY OPTIONS SCANNER - 2026-01-18 10:35:15
════════════════════════════════════════════════════════════════════════════════
  Expiry: 20-Jan-2026 | Strike Range: 25000 - 26000
  Premium Range: ₹80 - ₹120 | NIFTY Spot: ₹25,480.50

  ──────────────────────────────────────────────────────────────────────────────
  📈 CALL OPTIONS (CE) - Premium ₹80-₹120
  ──────────────────────────────────────────────────────────────────────────────
  | Symbol              | Strike | LTP     | Change  | Expiry      |
  |---------------------|--------|---------|---------|-------------|
  | NIFTY2612025500CE   | 25500  | ₹95.50  | +2.35%  | 20-Jan-2026 |
  | NIFTY2612025550CE   | 25550  | ₹82.75  | +1.80%  | 20-Jan-2026 |
  | NIFTY2612025450CE   | 25450  | ₹115.25 | +3.15%  | 20-Jan-2026 |
  
  Total CE Options Found: 3

  ──────────────────────────────────────────────────────────────────────────────
  📉 PUT OPTIONS (PE) - Premium ₹80-₹120
  ──────────────────────────────────────────────────────────────────────────────
  | Symbol              | Strike | LTP     | Change  | Expiry      |
  |---------------------|--------|---------|---------|-------------|
  | NIFTY2612025400PE   | 25400  | ₹88.50  | -1.25%  | 20-Jan-2026 |
  | NIFTY2612025350PE   | 25350  | ₹105.00 | -0.95%  | 20-Jan-2026 |
  
  Total PE Options Found: 2
════════════════════════════════════════════════════════════════════════════════
  Scan #1 | Last Updated: 10:35:15 | Next Update: 10:35:20 (5s)
════════════════════════════════════════════════════════════════════════════════
```

---

## API Endpoints Used

| API Method | Purpose | Rate Limit |
|------------|---------|------------|
| `kite.instruments("NFO")` | Get all NFO instruments (once at startup) | No limit |
| `kite.ltp(instruments)` | Get live LTP (every 5 seconds) | 1 req/sec |
| `kite.quote(instruments)` | Get detailed quote with OHLC | 1 req/sec |

### API Response Structure

```python
# kite.ltp() response
{
    "NFO:NIFTY2612025500CE": {
        "instrument_token": 12345678,
        "last_price": 95.50
    },
    "NFO:NIFTY2612025500PE": {
        "instrument_token": 12345679,
        "last_price": 88.50
    }
}

# kite.quote() response (more detailed)
{
    "NFO:NIFTY2612025500CE": {
        "instrument_token": 12345678,
        "last_price": 95.50,
        "ohlc": {
            "open": 92.00,
            "high": 98.25,
            "low": 90.50,
            "close": 93.00  # Previous day close
        },
        "net_change": 2.50,
        "volume": 125000,
        "oi": 500000
    }
}
```

---

## Class Structure

```
NiftyOptionsScanner
├── __init__(kite_client, config)
│   ├── Strike range configuration (min, max)
│   ├── Premium range configuration (min, max)
│   ├── Refresh interval
│   └── Instrument cache
│
├── load_nifty_options()
│   └── Fetch and cache all NIFTY options from NFO
│
├── filter_by_strike_range(options)
│   └── Filter options within strike range
│
├── get_live_prices(options)
│   └── Fetch LTP for all filtered options
│
├── filter_by_premium_range(options_with_prices)
│   └── Filter options with premium between 80-120
│
├── display_results(ce_options, pe_options)
│   └── Pretty print the filtered options
│
└── run()
    └── Main loop running every 5 seconds
```

---

## Error Handling

| Error | Handling | Recovery |
|-------|----------|----------|
| API Rate Limit | Exponential backoff | Retry after delay |
| Network Timeout | Catch exception | Continue to next cycle |
| Invalid Token | Log and skip | Remove from cache |
| Market Closed | Display message | Continue monitoring |

---

## Use Cases

### 1. Finding Affordable Options
Options with premium between ₹80-₹120 are affordable for retail traders while still having good liquidity.

### 2. Strategy Selection
- **CE Options in Range**: Potential BUY candidates for bullish outlook
- **PE Options in Range**: Potential BUY candidates for bearish outlook

### 3. Spread Building
Options in similar premium ranges can be used to build spreads (Bull Call, Bear Put, etc.)

---

## Consequences

### Positive
1. **Real-time Monitoring** - Live data every 5 seconds
2. **Focused Search** - Only shows relevant options
3. **Easy Integration** - Can be extended for trading strategies
4. **Low API Usage** - Efficient batch LTP requests

### Negative
1. **API Dependency** - Requires stable Kite Connect connection
2. **Market Hours Only** - Live data only during trading hours
3. **Limited to NIFTY** - Single underlying (can be extended)

### Risks
| Risk | Mitigation |
|------|------------|
| Stale Data | 5-second refresh ensures near real-time data |
| High Volatility | Premium filters may miss rapidly moving options |
| Expiry Confusion | Clear expiry display in output |

---

## Configuration File

```python
# config.py - Scanner Configuration

SCANNER_CONFIG = {
    # Expiry Date (User Input)
    # Supported formats: "Jan 20", "20 Jan", "Jan 20 2026", "2026-01-20"
    "expiry_date": "Jan 20",  # Specific expiry date
    
    # Strike Price Range
    "strike_min": 25000,
    "strike_max": 26000,
    "strike_multiple": 100,  # Only strikes in multiples of 100
    
    # Premium Range
    "premium_min": 80,
    "premium_max": 120,
    
    # Timing
    "refresh_interval_seconds": 5,
    
    # Filters
    "underlying": "NIFTY",
    "exchange": "NFO",
    "option_types": ["CE", "PE"],
}
```

---

## Usage Examples

### Interactive Mode (with User Input)
```bash
python nifty_options_scanner.py
```
This will prompt for expiry date input.

### Programmatic Mode
```python
from nifty_options_scanner import NiftyOptionsScanner, run_with_expiry

# Quick run with expiry date (strikes in multiples of 100 by default)
run_with_expiry("Jan 20")  # Uses Jan 20 expiry

# Include all strikes (multiples of 50)
run_with_expiry("Jan 20", strike_multiple=50)

# Full configuration
config = {
    "expiry_date": "Jan 20",  # or "20 Jan 2026", "2026-01-20"
    "strike_min": 25000,
    "strike_max": 26000,
    "strike_multiple": 100,   # Only 25000, 25100, 25200, etc. (not 25050, 25150)
    "premium_min": 80,
    "premium_max": 120,
    "refresh_interval_seconds": 5
}

scanner = NiftyOptionsScanner(config=config)
scanner.run()

# Single scan (for integration with other systems)
result = scanner.get_filtered_options()
print(result['ce_options'])  # Filtered CE options
print(result['pe_options'])  # Filtered PE options
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pandas | Latest | Data manipulation |
| kiteconnect | Latest | Zerodha API integration |
| python-dotenv | Latest | Environment variables |
| tabulate | Latest | Pretty table output (optional) |

---

## Related Documents

- `nifty_options_scanner.py` - Main scanner implementation
- `kite_client.py` - Kite API wrapper
- `ADR-001` - NIFTY CE Option Strategy
- `ADR-002` - NIFTY PE Option Strategy

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Team | Initial Options Scanner ADR |
