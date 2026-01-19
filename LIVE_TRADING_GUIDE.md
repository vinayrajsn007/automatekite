# NIFTY Options Auto Trader - Live Trading Guide

This guide explains how to run the NIFTY CE (Call) and PE (Put) auto traders with live Kite Connect API.

---

## Prerequisites

### 1. Zerodha Kite Connect API Setup

1. **Get API Credentials** from [https://kite.trade/](https://kite.trade/)
   - Login to Kite Connect Developer Console
   - Create a new app (if not already created)
   - Note down your **API Key** and **API Secret**

2. **Create `.env` file** in the project directory:
   ```bash
   cd /Users/vinayraj/Desktop/vinay/kite/17-jan
   ```
   
   Create `.env` with your credentials:
   ```
   KITE_API_KEY=your_api_key_here
   KITE_API_SECRET=your_api_secret_here
   KITE_ACCESS_TOKEN=
   ```

### 2. Install Dependencies

```bash
pip install kiteconnect pandas numpy python-dotenv pytz
```

Or using requirements.txt:
```bash
pip install -r requirements.txt
```

---

## Step 1: Generate Access Token (Daily Requirement)

**Important:** Access token expires daily at 6:00 AM IST. You must regenerate it each trading day.

### Option A: Using auth_helper.py (Interactive)

```bash
cd /Users/vinayraj/Desktop/vinay/kite/17-jan
python3 auth_helper.py
```

Follow the prompts:
1. Enter your API Key
2. Enter your API Secret
3. Browser will open for Zerodha login
4. After login, copy the `request_token` from the redirect URL
5. Paste the request token
6. Save token to `.env` when prompted

### Option B: Manual Token Generation

1. Open browser and go to:
   ```
   https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_API_KEY
   ```

2. Login with your Zerodha credentials

3. After login, you'll be redirected to a URL like:
   ```
   https://your-redirect-url.com?request_token=XXXXXX&action=login&status=success
   ```

4. Copy the `request_token` value

5. Generate access token using Python:
   ```python
   from kiteconnect import KiteConnect
   
   kite = KiteConnect(api_key="YOUR_API_KEY")
   data = kite.generate_session("REQUEST_TOKEN", api_secret="YOUR_API_SECRET")
   print(f"Access Token: {data['access_token']}")
   ```

6. Update `.env` file:
   ```
   KITE_ACCESS_TOKEN=your_new_access_token
   ```

---

## Step 2: Test Connection

Before running live trades, always test your connection:

### Test CE Trader Connection:
```bash
python3 nifty_call_option_strategy.py --test
```

### Test PE Trader Connection:
```bash
python3 nifty_put_option_strategy.py --test
```

Expected output:
```
  TESTING KITE CONNECTION
============================================================

  Connected Successfully!
  User: Your Name (YOUR_USER_ID)
  Email: your@email.com
  Balance: ₹XX,XXX.XX
  NIFTY 50: ₹XX,XXX.XX

  All tests passed! Ready for trading.
============================================================
```

---

## Step 3: Run in Simulation Mode (Recommended First)

Test the strategy without placing real orders:

### CE (Call Options) Simulation:
```bash
python3 nifty_call_option_strategy.py --simulation --expiry "Jan 23"
```

### PE (Put Options) Simulation:
```bash
python3 nifty_put_option_strategy.py --simulation --expiry "Jan 23"
```

**Expiry Date Formats:**
- `"Jan 23"` - Short format (current year assumed)
- `"2026-01-23"` - Full date format (YYYY-MM-DD)

---

## Step 4: Run LIVE Trading

### CALL Options (CE) - Live Mode:
```bash
python3 nifty_call_option_strategy.py --live --expiry "Jan 23"
```

### PUT Options (PE) - Live Mode:
```bash
python3 nifty_put_option_strategy.py --live --expiry "Jan 23"
```

**Confirmation Required:**
When running in live mode, you'll be prompted:
```
  WARNING: LIVE TRADING MODE - REAL ORDERS WILL BE PLACED!
============================================================
  Type 'YES' to confirm:
```

Type `YES` (all caps) to start live trading.

---

## Command Line Options

| Option | Description |
|--------|-------------|
| `--live` | Run in LIVE mode (real orders) |
| `--simulation` | Run in simulation mode (no real orders) |
| `--test` | Test Kite connection only |
| `--expiry "Jan 23"` | Set expiry date (short format) |
| `--expiry "2026-01-23"` | Set expiry date (full format) |

### Examples:

```bash
# Test connection
python3 nifty_call_option_strategy.py --test

# Simulation with expiry
python3 nifty_put_option_strategy.py --simulation --expiry "Jan 30"

# Live trading CE options
python3 nifty_call_option_strategy.py --live --expiry "2026-01-23"

# Live trading PE options
python3 nifty_put_option_strategy.py --live --expiry "2026-01-23"
```

---

## Trading Configuration

Both traders use the following default configuration (from ADR-004 and ADR-005):

| Parameter | Value | Description |
|-----------|-------|-------------|
| Strike Range | 25000-26000 | NIFTY strike price range |
| Premium Range | ₹80-₹120 | Option premium filter |
| Risk Factor | 40% | Percentage of balance to use |
| Lot Size | 75 | NIFTY lot size |
| Market Open | 9:15 AM IST | Trading start time |
| Market Close | 3:30 PM IST | Trading end time |
| Skip Opening | 15 minutes | Skip 9:15-9:30 AM (volatile) |
| Stop New Trades | 15 min before close | No new trades after 3:15 PM |

---

## Strategy Logic

### Entry (Double Confirmation)
Both 5-minute AND 2-minute timeframes must show:
- SuperTrend (7,3) = Bullish
- Price > SuperTrend value
- Price > EMA Low (8)
- EMA 8 > EMA 9
- StochRSI < 50 OR rising
- RSI < 65 AND rising
- MACD histogram > 0 OR improving

### Exit Conditions
Exit when any of these occur:
1. **EMA Low Falling**: EMA Low decreasing for 3 candles AND price below EMA Low
2. **Strong Bearish**: SuperTrend bearish + EMA 8 < EMA 9 + Price below EMA Low
3. **Market Close**: Force exit at 3:30 PM IST

---

## Daily Trading Workflow

### Morning Setup (Before 9:15 AM):

1. **Check Token** - Regenerate if needed:
   ```bash
   python3 auth_helper.py
   ```

2. **Test Connection**:
   ```bash
   python3 nifty_call_option_strategy.py --test
   ```

3. **Check Expiry Dates** - Find the nearest weekly/monthly expiry

4. **Start Trader** (after 9:15 AM):
   ```bash
   # For CALL options
   python3 nifty_call_option_strategy.py --live --expiry "Jan 23"
   
   # OR for PUT options
   python3 nifty_put_option_strategy.py --live --expiry "Jan 23"
   ```

### During Market Hours:
- Trader runs automatically
- Monitors for entry/exit signals
- Places orders when conditions are met
- Displays real-time status

### End of Day:
- Trader shows daily summary
- All positions are closed by 3:30 PM
- Press Ctrl+C to stop manually if needed

---

## Monitoring the Trader

The trader displays real-time information:

```
================================================================================
  NIFTY CE AUTO TRADER - 2026-01-23 10:35:15
  MODE: LIVE | TRADE CYCLE #2
================================================================================

  MARKET STATUS
  ----------------------------------------------------------------------------
  Market: OPEN | Time to Close: 295 minutes

  ACCOUNT STATUS
  ----------------------------------------------------------------------------
  Available Balance: ₹50,000.00
  Trading Capital (40%): ₹20,000.00

  SELECTED OPTION (via Scanner)
  ----------------------------------------------------------------------------
  Symbol: NIFTY26JAN25500CE
  Strike: 25500
  Expiry: 2026-01-23
  Premium: ₹95.50

  DOUBLE CONFIRMATION STATUS
  ----------------------------------------------------------------------------
  NIFTY Spot: ₹25,480.50

  | Indicator      | 5-MIN    | 2-MIN    |
  |----------------|----------|----------|
  | SuperTrend     | BULLISH  | BULLISH  |
  | EMA Cross      | 8 > 9    | 8 > 9    |
  | RSI            | 58.5     | 55.2     |
  | StochRSI       | 35.2     | 42.1     |
  | MACD Hist      | 2.15     | 1.85     |

  PRIMARY SIGNAL (5-min): BUY
  CONFIRM SIGNAL (2-min): BUY
```

---

## Troubleshooting

### Error: "No access token found"
```bash
# Regenerate token
python3 auth_helper.py
```

### Error: "Token is invalid or expired"
- Access tokens expire daily at 6 AM IST
- Generate a new token using auth_helper.py

### Error: "Insufficient balance"
- Check your Zerodha account balance
- Ensure you have enough margin for options trading
- Trader uses 40% of available balance by default

### Error: "No options in premium range"
- Market may be volatile
- Premium range is ₹80-₹120
- Wait for options to come into range or adjust config

### Error: "Connection refused"
- Check internet connection
- Verify Kite API is not down
- Check if market is open

---

## Important Notes

1. **Risk Warning**: Options trading involves substantial risk. Only trade with capital you can afford to lose.

2. **Token Expiry**: Remember to regenerate access token daily before 9:15 AM.

3. **Market Hours**: Trader only operates during market hours (9:15 AM - 3:30 PM IST).

4. **First 15 Minutes**: Trader skips the first 15 minutes due to market volatility.

5. **Position Sizing**: Uses 40% of your balance (configurable in code).

6. **Continuous Mode**: After each trade exit, it automatically looks for the next trade until market closes.

7. **Manual Override**: Press Ctrl+C anytime to stop the trader (warning: may leave open positions).

---

## File Structure

```
/Users/vinayraj/Desktop/vinay/kite/17-jan/
├── .env                          # API credentials (create this)
├── config.py                     # Configuration loader
├── auth_helper.py                # Token generation helper
├── nifty_call_option_strategy.py # CE (Call) Auto Trader
├── nifty_put_option_strategy.py  # PE (Put) Auto Trader
├── requirements.txt              # Python dependencies
└── LIVE_TRADING_GUIDE.md         # This guide
```

---

## Quick Start Commands

```bash
# Navigate to project
cd /Users/vinayraj/Desktop/vinay/kite/17-jan

# Step 1: Generate token (do this daily)
python3 auth_helper.py

# Step 2: Test connection
python3 nifty_call_option_strategy.py --test

# Step 3: Run simulation first
python3 nifty_call_option_strategy.py --simulation --expiry "Jan 23"

# Step 4: Go live (when ready)
python3 nifty_call_option_strategy.py --live --expiry "Jan 23"
```

---

## Support

- **ADR Documentation**: See ADR-004 (CE) and ADR-005 (PE) for strategy details
- **Kite Connect Docs**: [https://kite.trade/docs/connect/v3/](https://kite.trade/docs/connect/v3/)

---

*Last Updated: January 2026*
