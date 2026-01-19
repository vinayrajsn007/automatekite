# Setup Guide: Live Trading with Zerodha Kite

## Current Status

❌ **Access Token Required** - Your Kite API credentials need to be configured or the access token has expired.

---

## Quick Setup (3 Steps)

### Step 1: Get Your Kite API Credentials

1. Go to [https://developers.kite.trade/](https://developers.kite.trade/)
2. Login with your Zerodha account
3. Create a new app (or use existing)
4. Note down:
   - **API Key**
   - **API Secret**

### Step 2: Generate Access Token

Run the authentication helper:

```bash
python3 auth_helper.py
```

This will:
1. Open browser for Kite login
2. After login, copy the `request_token` from URL
3. Generate a fresh access token
4. Save it to `.env` file

**OR manually update `.env` file:**

```bash
# Create or edit .env file
nano .env

# Add these lines:
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
```

### Step 3: Test Connection

```bash
python3 test_live_connection.py
```

---

## Access Token Expiry

⚠️ **Important:** Kite access tokens expire **daily at 6:00 AM**. You need to regenerate them each trading day.

### Auto-Refresh Solution (Optional)

Create a startup script that runs before market opens:

```bash
# Run at 8:30 AM daily (before market)
python3 auth_helper.py
```

---

## What the Live System Will Do

Once connected, the `test_live_connection.py` script will:

1. ✅ Verify connection to Kite
2. 📊 Fetch live NIFTY 50 data (5-min and 2-min)
3. 🔢 Calculate all 6 technical indicators
4. 🎯 Check BUY/SELL signals in real-time
5. 📋 Display trading decision:
   - **DOUBLE CONFIRMATION** → BUY Call Option
   - **Single signal** → Wait for confirmation
   - **SELL signal** → Exit position

---

## For Today: Mock Test Available

Since live connection requires token setup, I've created a **simulated test** using recent market conditions:

```bash
python3 test_live_connection_mock.py
```

This will show you:
- How the live system displays data
- Real-time indicator calculations
- Signal generation logic
- Trading decisions

---

## Security Notes

1. **Never commit** `.env` file to git (already in `.gitignore`)
2. **Regenerate tokens** daily before trading
3. **Keep API Secret** confidential
4. **Use Paper Trading** first (simulation mode)

---

## Troubleshooting

### Error: "Incorrect api_key or access_token"

**Solution:** Token expired. Run `python3 auth_helper.py` to generate new token.

### Error: "No module named 'kiteconnect'"

**Solution:** Install dependencies:
```bash
pip install kiteconnect python-dotenv pandas numpy
```

### Error: "ValueError: API Key and API Secret are required"

**Solution:** Your `.env` file is missing or empty. Follow Step 2 above.

---

## Ready to Go Live?

Once your `.env` is configured:

1. **Test connection:**
   ```bash
   python3 test_live_connection.py
   ```

2. **Run paper trading:**
   ```bash
   python3 nifty_strategy.py --simulation
   ```

3. **Start live trading** (when confident):
   ```bash
   python3 nifty_strategy.py --live
   ```

---

## Next Steps

1. ✅ Verify backtest results (Done - +15.64% ROI on Jan 16)
2. 🔄 Setup Kite credentials (You are here)
3. 📊 Test live data connection
4. 🎯 Paper trade for 5-10 days
5. 💰 Go live with minimum lot size

---

**Need Help?** Check the error messages carefully - they usually tell you exactly what's missing!
